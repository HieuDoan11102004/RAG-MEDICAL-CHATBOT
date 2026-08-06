"""Isolated tests for the repository configuration contract."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.common.custom_exception import CustomException
from app.components import embeddings, llm
from app.config.config import (
    PROJECT_ROOT,
    ConfigurationError,
    get_openai_api_key,
    load_settings,
)


DEFAULT_CONFIG = """\
openai_model: gpt-4.1-mini
openai_embedding_model: text-embedding-3-small
db_faiss_path: vectorstore/db_faiss
data_path: data
chunk_size: 500
chunk_overlap: 50
"""


class ConfigurationLoaderTests(unittest.TestCase):
    """Exercise only explicit temporary configuration sources."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.config_path = self.directory / "config.yaml"
        self.dotenv_path = self.directory / ".env"
        self.write_config(DEFAULT_CONFIG)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write_config(self, content: str) -> None:
        self.config_path.write_text(content, encoding="utf-8")

    def write_dotenv(self, content: str) -> None:
        self.dotenv_path.write_text(content, encoding="utf-8")

    def load(self, environ: dict[str, str] | None = None):
        return load_settings(
            config_path=self.config_path,
            dotenv_path=self.dotenv_path,
            environ={} if environ is None else environ,
        )

    def assert_configuration_error(self, content: str, field: str | None = None) -> None:
        self.write_config(content)
        with self.assertRaises(ConfigurationError) as raised:
            self.load()
        if field:
            self.assertIn(field, str(raised.exception))

    def test_committed_config_has_exact_schema_and_current_defaults(self) -> None:
        committed_keys = {
            line.partition(":")[0]
            for line in (PROJECT_ROOT / "config.yaml").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        self.assertEqual(
            committed_keys,
            {
                "openai_model",
                "openai_embedding_model",
                "db_faiss_path",
                "data_path",
                "chunk_size",
                "chunk_overlap",
            },
        )

        settings = load_settings(
            config_path=PROJECT_ROOT / "config.yaml",
            dotenv_path=PROJECT_ROOT / "missing-test-dotenv",
            environ={},
        )
        self.assertEqual(settings.openai_model, "gpt-4.1-mini")
        self.assertEqual(settings.openai_embedding_model, "text-embedding-3-small")
        self.assertEqual(settings.data_path, PROJECT_ROOT / "data")
        self.assertEqual(settings.db_faiss_path, PROJECT_ROOT / "vectorstore" / "db_faiss")
        self.assertEqual(settings.chunk_size, 500)
        self.assertEqual(settings.chunk_overlap, 50)

    def test_dotenv_overrides_each_supported_setting_without_leaking(self) -> None:
        overrides = {
            "OPENAI_MODEL": "dotenv-chat",
            "OPENAI_EMBEDDING_MODEL": "dotenv-embedding",
            "DATA_PATH": "dotenv-data",
            "DB_FAISS_PATH": "dotenv-index",
            "CHUNK_SIZE": "600",
            "CHUNK_OVERLAP": "60",
        }
        self.write_dotenv("\n".join(f"{key}={value}" for key, value in overrides.items()))

        settings = self.load()
        self.assertEqual(settings.openai_model, "dotenv-chat")
        self.assertEqual(settings.openai_embedding_model, "dotenv-embedding")
        self.assertEqual(settings.data_path, PROJECT_ROOT / "dotenv-data")
        self.assertEqual(settings.db_faiss_path, PROJECT_ROOT / "dotenv-index")
        self.assertEqual(settings.chunk_size, 600)
        self.assertEqual(settings.chunk_overlap, 60)
        self.assertNotIn("OPENAI_MODEL", os.environ)

        self.dotenv_path.unlink()
        reloaded = self.load()
        self.assertEqual(reloaded.openai_model, "gpt-4.1-mini")
        self.assertEqual(reloaded.chunk_size, 500)

    def test_process_environment_overrides_dotenv_for_every_supported_setting(self) -> None:
        dotenv_overrides = {
            "OPENAI_MODEL": "dotenv-chat",
            "OPENAI_EMBEDDING_MODEL": "dotenv-embedding",
            "DATA_PATH": "dotenv-data",
            "DB_FAISS_PATH": "dotenv-index",
            "CHUNK_SIZE": "600",
            "CHUNK_OVERLAP": "60",
        }
        process_overrides = {
            "OPENAI_MODEL": "process-chat",
            "OPENAI_EMBEDDING_MODEL": "process-embedding",
            "DATA_PATH": "process-data",
            "DB_FAISS_PATH": "process-index",
            "CHUNK_SIZE": "700",
            "CHUNK_OVERLAP": "70",
        }
        self.write_dotenv("\n".join(f"{key}={value}" for key, value in dotenv_overrides.items()))
        settings = self.load(process_overrides)

        self.assertEqual(settings.openai_model, "process-chat")
        self.assertEqual(settings.openai_embedding_model, "process-embedding")
        self.assertEqual(settings.data_path, PROJECT_ROOT / "process-data")
        self.assertEqual(settings.db_faiss_path, PROJECT_ROOT / "process-index")
        self.assertEqual(settings.chunk_size, 700)
        self.assertEqual(settings.chunk_overlap, 70)

    def test_relative_and_absolute_paths_are_deterministic_outside_project_root(self) -> None:
        previous_directory = Path.cwd()
        outside_project = self.directory / "outside-project"
        outside_project.mkdir()
        try:
            os.chdir(outside_project)
            relative_settings = self.load()
        finally:
            os.chdir(previous_directory)

        self.assertEqual(relative_settings.data_path, PROJECT_ROOT / "data")
        self.assertEqual(relative_settings.db_faiss_path, PROJECT_ROOT / "vectorstore" / "db_faiss")

        absolute_data = self.directory / "absolute-data"
        absolute_index = self.directory / "absolute-index"
        absolute_settings = self.load(
            {"DATA_PATH": str(absolute_data), "DB_FAISS_PATH": str(absolute_index)}
        )
        self.assertEqual(absolute_settings.data_path, absolute_data)
        self.assertEqual(absolute_settings.db_faiss_path, absolute_index)

    def test_invalid_yaml_documents_raise_configuration_errors(self) -> None:
        for content, field in (
            ("[not, a, mapping]", "mapping"),
            ("", "empty"),
            ("openai_model: [", "Invalid YAML"),
            (DEFAULT_CONFIG + "openai_model: duplicate\n", "duplicate key"),
            (DEFAULT_CONFIG.replace("chunk_overlap: 50\n", ""), "missing"),
            (DEFAULT_CONFIG + "unexpected: value\n", "unknown"),
        ):
            with self.subTest(content=content):
                self.assert_configuration_error(content, field)

        with self.assertRaises(ConfigurationError) as raised:
            load_settings(config_path=self.directory, dotenv_path=self.dotenv_path, environ={})
        self.assertIn("Unable to read", str(raised.exception))

    def test_complex_yaml_mapping_key_raises_configuration_error(self) -> None:
        self.write_config(DEFAULT_CONFIG + "? [non, hashable]\n: value\n")

        with self.assertRaises(ConfigurationError):
            self.load()

    def test_each_field_rejects_a_wrong_yaml_type_or_blank_string(self) -> None:
        invalid_values = {
            "openai_model": "42",
            "openai_embedding_model": "42",
            "db_faiss_path": "42",
            "data_path": "42",
            "chunk_size": '"500"',
            "chunk_overlap": '"50"',
        }
        for field, invalid_value in invalid_values.items():
            with self.subTest(field=field):
                content = DEFAULT_CONFIG.replace(
                    next(line for line in DEFAULT_CONFIG.splitlines() if line.startswith(f"{field}:")),
                    f"{field}: {invalid_value}",
                )
                self.assert_configuration_error(content, field)

        for field in ("openai_model", "openai_embedding_model", "db_faiss_path", "data_path"):
            with self.subTest(blank_field=field):
                content = DEFAULT_CONFIG.replace(
                    next(line for line in DEFAULT_CONFIG.splitlines() if line.startswith(f"{field}:")),
                    f'{field}: "   "',
                )
                self.assert_configuration_error(content, field)

    def test_invalid_numeric_values_are_rejected(self) -> None:
        for field, value in (
            ("chunk_size", "true"),
            ("chunk_size", "0"),
            ("chunk_size", "-1"),
            ("chunk_overlap", "true"),
            ("chunk_overlap", "-1"),
        ):
            with self.subTest(field=field, value=value):
                content = DEFAULT_CONFIG.replace(
                    next(line for line in DEFAULT_CONFIG.splitlines() if line.startswith(f"{field}:")),
                    f"{field}: {value}",
                )
                self.assert_configuration_error(content, field)

        self.assert_configuration_error(
            DEFAULT_CONFIG.replace("chunk_overlap: 50", "chunk_overlap: 500"), "chunk_overlap"
        )
        for environ in ({"CHUNK_SIZE": "not-an-integer"}, {"CHUNK_OVERLAP": "-1"}):
            with self.subTest(environ=environ):
                with self.assertRaises(ConfigurationError):
                    self.load(environ)

    def test_api_key_is_not_yaml_configuration_and_is_read_non_mutatingly(self) -> None:
        self.assertNotIn("OPENAI_API_KEY", (PROJECT_ROOT / "config.yaml").read_text(encoding="utf-8"))
        self.assert_configuration_error(DEFAULT_CONFIG + "OPENAI_API_KEY: forbidden\n", "unknown")

        self.write_dotenv("OPENAI_API_KEY=dotenv-secret\n")
        self.assertEqual(get_openai_api_key(environ={}, dotenv_path=self.dotenv_path), "dotenv-secret")
        self.assertEqual(
            get_openai_api_key(environ={"OPENAI_API_KEY": "process-secret"}, dotenv_path=self.dotenv_path),
            "process-secret",
        )
        self.assertIsNone(get_openai_api_key(environ={}, dotenv_path=self.directory / "missing.env"))

    def test_llm_rejects_missing_api_key_before_constructing_client(self) -> None:
        with (
            patch.object(llm, "get_openai_api_key", return_value=None) as get_api_key,
            patch.object(llm, "ChatOpenAI") as chat_openai,
            self.assertRaises(CustomException) as raised,
        ):
            llm.load_llm()

        get_api_key.assert_called_once_with()
        chat_openai.assert_not_called()
        self.assertIn("OPENAI_API_KEY is not set", str(raised.exception))

    def test_embeddings_reject_missing_api_key_before_constructing_client(self) -> None:
        with (
            patch.object(embeddings, "get_openai_api_key", return_value=None) as get_api_key,
            patch.object(embeddings, "OpenAIEmbeddings") as embedding_client,
            self.assertRaises(CustomException) as raised,
        ):
            embeddings.get_embedding_model()

        get_api_key.assert_called_once_with()
        embedding_client.assert_not_called()
        self.assertIn("OPENAI_API_KEY is not set", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
