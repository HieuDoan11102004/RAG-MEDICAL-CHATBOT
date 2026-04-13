import sys


class CustomException(Exception):
    def __init__(self, message: str, error_detail: Exception = None):
        self.error_message = self.get_detailed_error_message(message, error_detail)
        super().__init__(self.error_message)

    @staticmethod
    def get_detailed_error_message(message, error_detail):
        _, _, exc_tb = sys.exc_info()
        if error_detail is not None and hasattr(error_detail, "__traceback__"):
            exc_tb = error_detail.__traceback__

        if exc_tb is not None:
            file_name = exc_tb.tb_frame.f_code.co_filename
            line_number = exc_tb.tb_lineno
        else:
            file_name = "N/A"
            line_number = "N/A"

        return (
            f"{message} | "
            f"Error: {error_detail} | "
            f"File Name: {file_name} | "
            f"Line Number: {line_number}"
        )
