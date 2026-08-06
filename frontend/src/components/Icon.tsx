import type { ReactNode, SVGProps } from "react";

type IconName = "plus" | "search" | "dots" | "paperclip" | "smile" | "send" | "trash" | "alert" | "chevron" | "bot" | "user";

const paths: Record<IconName, ReactNode> = {
  plus: <path d="M12 5v14M5 12h14" />,
  search: <><circle cx="11" cy="11" r="6" /><path d="m16 16 4 4" /></>,
  dots: <><circle cx="5" cy="12" r="1" fill="currentColor" /><circle cx="12" cy="12" r="1" fill="currentColor" /><circle cx="19" cy="12" r="1" fill="currentColor" /></>,
  paperclip: <path d="m8.5 12.5 6.7-6.7a3 3 0 0 1 4.2 4.3l-8.6 8.6a5 5 0 0 1-7.1-7.1l8.1-8.1" />,
  smile: <><circle cx="12" cy="12" r="8" /><path d="M8.5 14.5c2 2 5 2 7 0M9 9h.01M15 9h.01" /></>,
  send: <path d="m21 3-7.2 18-3.7-7.3L3 10.1 21 3Z M10.1 13.7 14 10" />,
  trash: <><path d="M4 7h16M10 11v6M14 11v6M9 7l1-3h4l1 3M6 7l1 14h10l1-14" /></>,
  alert: <><path d="M12 3 2.8 19h18.4L12 3Z" /><path d="M12 9v4M12 16h.01" /></>,
  chevron: <path d="m9 18 6-6-6-6" />,
  bot: <><rect x="4" y="7" width="16" height="12" rx="4" /><path d="M12 4v3M8 12h.01M16 12h.01M9 16h6" /></>,
  user: <><circle cx="12" cy="8" r="3.5" /><path d="M5.5 20c.7-3.3 2.8-5 6.5-5s5.8 1.7 6.5 5" /></>,
};

export function Icon({ name, ...props }: { name: IconName } & SVGProps<SVGSVGElement>) {
  return <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...props}>{paths[name]}</svg>;
}
