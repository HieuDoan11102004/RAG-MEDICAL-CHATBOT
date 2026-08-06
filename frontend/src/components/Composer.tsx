import { FormEvent, useState } from "react";
import { Icon } from "./Icon";

export function Composer({ onSend, disabled }: { onSend: (prompt: string) => void; disabled: boolean }) {
  const [prompt, setPrompt] = useState("");
  function submit(event: FormEvent) {
    event.preventDefault();
    const value = prompt.trim();
    if (!value || disabled) return;
    onSend(value);
    setPrompt("");
  }
  return <form className="composer" onSubmit={submit}>
    <label className="sr-only" htmlFor="chat-prompt">Ask a medical question</label>
    <button type="button" className="composer-icon" aria-label="Attach a file (not available yet)"><Icon name="paperclip" /></button>
    <input id="chat-prompt" value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Message MedChat..." disabled={disabled} autoComplete="off" />
    <button type="button" className="composer-icon" aria-label="Add emoji (not available yet)"><Icon name="smile" /></button>
    <button className="send-button" type="submit" aria-label="Send message" disabled={disabled || !prompt.trim()}><Icon name="send" /></button>
  </form>;
}
