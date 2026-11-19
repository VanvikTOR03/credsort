import React from "react";

// A small, consistent glyph set: filled, rounded, one idea per icon (recognition over recall).
const G: Record<string, React.ReactNode> = {
  home: <path d="M12 3.1 3.2 10.4a1 1 0 0 0-.4.8V20a1 1 0 0 0 1 1H9v-5.5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1V21h5.2a1 1 0 0 0 1-1v-8.8a1 1 0 0 0-.4-.8L12 3.1z" />,
  chart: <><rect x="3.5" y="12" width="4.4" height="8.5" rx="1.4" /><rect x="9.8" y="7" width="4.4" height="13.5" rx="1.4" /><rect x="16.1" y="3" width="4.4" height="17.5" rx="1.4" /></>,
  loan: <path fillRule="evenodd" d="M5.5 6h13A2.5 2.5 0 0 1 21 8.5v7a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 15.5v-7A2.5 2.5 0 0 1 5.5 6zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM5.6 9.4a.9.9 0 1 0 0 1.8.9.9 0 0 0 0-1.8zm12.8 3.4a.9.9 0 1 0 0 1.8.9.9 0 0 0 0-1.8z" />,
  shield: <path fillRule="evenodd" d="M12 2.4 4.2 5.5v5.8c0 4.9 3.2 8.5 7.8 10.3 4.6-1.8 7.8-5.4 7.8-10.3V5.5L12 2.4zm-1.1 13.7-3.1-3.1 1.5-1.5 1.6 1.6 4-4 1.5 1.5-5.5 5.5z" />,
  more: <><circle cx="5.5" cy="12" r="2.1" /><circle cx="12" cy="12" r="2.1" /><circle cx="18.5" cy="12" r="2.1" /></>,
  grid: <><rect x="3.5" y="3.5" width="7" height="7" rx="2" /><rect x="13.5" y="3.5" width="7" height="7" rx="2" /><rect x="3.5" y="13.5" width="7" height="7" rx="2" /><rect x="13.5" y="13.5" width="7" height="7" rx="2" /></>,
  bell: <path d="M12 2.8a6 6 0 0 0-6 6V12c0 1.5-.6 2.6-1.6 3.8-.6.7-.1 1.7.8 1.7h13.6c.9 0 1.4-1 .8-1.7C18.6 14.6 18 13.5 18 12V8.8a6 6 0 0 0-6-6zM9.4 19.2a2.7 2.7 0 0 0 5.2 0H9.4z" />,
  plug: <path d="M8 2.8v5H6.2a1 1 0 0 0-1 1V11a6.8 6.8 0 0 0 5.8 6.7V21.2h2v-3.5A6.8 6.8 0 0 0 18.8 11V8.8a1 1 0 0 0-1-1H16v-5h-2v5h-4v-5H8z" />,
  upload: <path d="M12 3.2 6.6 8.6l1.5 1.5L11 7.2V16h2V7.2l2.9 2.9 1.5-1.5L12 3.2zM4 14.5V19a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4.5h-2V19H6v-4.5H4z" />,
  check: <path d="M9.4 16.3 5.7 12.6l-1.6 1.6 5.3 5.3L20 8.9l-1.6-1.6-9 9z" />,
  user: <><circle cx="12" cy="7.8" r="4.2" /><path d="M3.8 20.2c0-3.9 3.7-6.3 8.2-6.3s8.2 2.4 8.2 6.3c0 .6-.5 1-1 1H4.8c-.5 0-1-.4-1-1z" /></>,
  people: <><circle cx="9" cy="8" r="3.6" /><path d="M2.5 19.6c0-3.4 2.9-5.5 6.5-5.5s6.5 2.1 6.5 5.5c0 .6-.4 1-1 1H3.5c-.6 0-1-.4-1-1z" /><circle cx="17.2" cy="8.8" r="2.8" opacity=".75" /><path d="M17.2 14.4c2.6 0 4.8 1.6 4.8 4.4 0 .5-.4.9-.9.9h-4.2c.2-.5.3-1.1.3-1.7 0-1.4-.4-2.7-1.2-3.7.4-.1.8-.2 1.2-.2z" opacity=".75" /></>,
  building: <path fillRule="evenodd" d="M5 21V4.6A1.6 1.6 0 0 1 6.6 3h6.8A1.6 1.6 0 0 1 15 4.6V9h3.4A1.6 1.6 0 0 1 20 10.6V21h-4.2v-4.2h-2.6V21H5zm3.2-14v2h2.2V7H8.2zm0 4.2v2h2.2v-2H8.2zm0 4.2v2h2.2v-2H8.2z" />,
  bank: <path d="M12 2.4 2.6 7.6v1.8h18.8V7.6L12 2.4zM5 11v6.4h2.6V11H5zm5.7 0v6.4h2.6V11h-2.6zm5.7 0v6.4H19V11h-2.6zM3 19v2.6h18V19H3z" />,
  franc: <path fillRule="evenodd" d="M12 2.8a9.2 9.2 0 1 0 0 18.4 9.2 9.2 0 0 0 0-18.4zm-3 5h6.3v1.7h-4.5v1.9h3.6v1.7h-3.6V17H9V7.8z" />,
  eye: <path fillRule="evenodd" d="M12 5c-5.4 0-9.2 3.9-10.5 7 1.3 3.1 5.1 7 10.5 7s9.2-3.9 10.5-7C21.2 8.9 17.4 5 12 5zm0 3.4a3.6 3.6 0 1 1 0 7.2 3.6 3.6 0 0 1 0-7.2z" />,
  eyeoff: <><path fillRule="evenodd" d="M12 5c-5.4 0-9.2 3.9-10.5 7 1.3 3.1 5.1 7 10.5 7s9.2-3.9 10.5-7C21.2 8.9 17.4 5 12 5zm0 3.4a3.6 3.6 0 1 1 0 7.2 3.6 3.6 0 0 1 0-7.2z" opacity=".55" /><path d="M3.7 5.1 5.1 3.7l15.2 15.2-1.4 1.4z" /></>,
  clock: <path fillRule="evenodd" d="M12 2.5a9.5 9.5 0 1 0 0 19 9.5 9.5 0 0 0 0-19zM11 6.6h2v5l3.5 2-1 1.7-4.5-2.6V6.6z" />,
  star: <path d="m12 2.8 2.7 5.6 6.1.8-4.5 4.2 1.1 6-5.4-3-5.4 3 1.1-6L3.2 9.2l6.1-.8L12 2.8z" />,
  spark: <><path d="M10.5 2.5c.7 5 3 7.3 8 8-5 .7-7.3 3-8 8-.7-5-3-7.3-8-8 5-.7 7.3-3 8-8z" /><path d="M19 14.5c.2 1.8 1 2.6 2.8 2.8-1.8.2-2.6 1-2.8 2.8-.2-1.8-1-2.6-2.8-2.8 1.8-.2 2.6-1 2.8-2.8z" /></>,
  sliders: <><rect x="3" y="5.2" width="18" height="2.2" rx="1.1" opacity=".5" /><rect x="3" y="10.9" width="18" height="2.2" rx="1.1" opacity=".5" /><rect x="3" y="16.6" width="18" height="2.2" rx="1.1" opacity=".5" /><circle cx="8" cy="6.3" r="3" /><circle cx="16" cy="12" r="3" /><circle cx="10" cy="17.7" r="3" /></>,
  refresh: <path d="M12 4.5a7.5 7.5 0 0 0-7.4 6.3h2.1A5.5 5.5 0 0 1 12 6.5c1.5 0 2.8.6 3.8 1.6L13.5 10.5H20V4l-2.7 2.7A7.5 7.5 0 0 0 12 4.5zm7.4 8.7a7.5 7.5 0 0 1-12.7 4.1L4 20v-6.5h6.5l-2.3 2.4a5.5 5.5 0 0 0 9.1-2.7h2.1z" />,
  plus: <path d="M11 4.5h2V11h6.5v2H13v6.5h-2V13H4.5v-2H11V4.5z" />,
  x: <path d="m6.3 4.9 5.7 5.7 5.7-5.7 1.4 1.4-5.7 5.7 5.7 5.7-1.4 1.4-5.7-5.7-5.7 5.7-1.4-1.4 5.7-5.7-5.7-5.7 1.4-1.4z" />,
  chevron: <path d="m8.6 3.8 8.2 8.2-8.2 8.2-1.5-1.5L13.8 12 7.1 5.3l1.5-1.5z" />,
  back: <path d="m15.4 3.8-8.2 8.2 8.2 8.2 1.5-1.5L10.2 12l6.7-6.7-1.5-1.5z" />,
  arrow: <path d="M4 11h12.2l-5.1-5.1 1.4-1.4 7.5 7.5-7.5 7.5-1.4-1.4 5.1-5.1H4v-2z" />,
  warning: <path fillRule="evenodd" d="M10.6 3.9a1.6 1.6 0 0 1 2.8 0l8.1 14.2a1.6 1.6 0 0 1-1.4 2.4H3.9a1.6 1.6 0 0 1-1.4-2.4l8.1-14.2zM11 9.5v4.8h2V9.5h-2zm1 6.6a1.2 1.2 0 1 0 0 2.4 1.2 1.2 0 0 0 0-2.4z" />,
  info: <path fillRule="evenodd" d="M12 2.5a9.5 9.5 0 1 0 0 19 9.5 9.5 0 0 0 0-19zm-1 8.5h2v6h-2v-6zm1-3.8a1.2 1.2 0 1 1 0 2.4 1.2 1.2 0 0 1 0-2.4z" />,
  calendar: <path fillRule="evenodd" d="M7 2.5h2V4.5h6V2.5h2V4.5h1.5A2.5 2.5 0 0 1 21 7v11.5a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 18.5V7a2.5 2.5 0 0 1 2.5-2.5H7v-2zM5 10v8.5c0 .3.2.5.5.5h13c.3 0 .5-.2.5-.5V10H5z" />,
  key: <path fillRule="evenodd" d="M8.5 4a6.5 6.5 0 1 1-2 12.7L5 18.2V20H3v-2.2l1.8-1.8L5 15.8A6.5 6.5 0 0 1 8.5 4zm1.5 3a2 2 0 1 0 0 4 2 2 0 0 0 0-4z" transform="translate(2 0)" />,
  doc: <path fillRule="evenodd" d="M6.5 2.5h7l5 5V19a2.5 2.5 0 0 1-2.5 2.5H6.5A2.5 2.5 0 0 1 4 19V5A2.5 2.5 0 0 1 6.5 2.5zM8 11v1.8h8V11H8zm0 3.6v1.8h8v-1.8H8zM13 3.8V8h4.2L13 3.8z" />,
  search: <path fillRule="evenodd" d="M10.5 3a7.5 7.5 0 1 0 4.5 13.5l4.5 4.5 1.5-1.5-4.5-4.5A7.5 7.5 0 0 0 10.5 3zm0 2.2a5.3 5.3 0 1 1 0 10.6 5.3 5.3 0 0 1 0-10.6z" />,
  mail: <path d="M5 4.5h14A2.5 2.5 0 0 1 21.5 7v.4L12 13 2.5 7.4V7A2.5 2.5 0 0 1 5 4.5zM2.5 9.7l9.5 5.6 9.5-5.6V17a2.5 2.5 0 0 1-2.5 2.5H5A2.5 2.5 0 0 1 2.5 17V9.7z" />,
  trash: <path d="M9 2.5h6l1 1.7h4v2H4v-2h4l1-1.7zM5.5 8h13l-1 11.5A2 2 0 0 1 15.5 21.3h-7a2 2 0 0 1-2-1.8L5.5 8z" />,
  send: <path d="M3.5 11.2 20.3 3.6c.8-.4 1.6.4 1.2 1.2l-7.6 16.8c-.4.9-1.7.8-1.9-.2L10.5 14 3.7 12.1c-1-.3-1.1-1.5-.2-1.9z" />,
  pencil: <path d="m15.2 4.3 4.5 4.5L9 19.5l-5.3 1 1-5.3L15.2 4.3zm1.4-1.4 1.1-1.1a1.7 1.7 0 0 1 2.4 0l2.1 2.1a1.7 1.7 0 0 1 0 2.4l-1.1 1.1-4.5-4.5z" transform="scale(.9) translate(1.3 1.3)" />,
  trend: <path d="M3 17.2 9.3 10.9l3.7 3.7 6-6V12h2V5.5h-6.5v2H17.6l-4.6 4.6L9.3 8.4 1.6 16 3 17.2z" />,
  gauge: <path fillRule="evenodd" d="M12 3a9.5 9.5 0 0 0-9.5 9.5c0 2.1.7 4 1.8 5.5h15.4a9.5 9.5 0 0 0 1.8-5.5A9.5 9.5 0 0 0 12 3zm4 4.5-3.2 4.8a1.8 1.8 0 1 1-1.6-1.1L16 7.5z" />,
  handshake: <path d="M2.5 9.5 7 6l3 1.8L13 6l4.5 3.5L21.5 8v7l-3.5 1.5-4.2 3.5-2-1.5-2 1.5-5-3.5L2.5 15V9.5z" />,
  lock: <path fillRule="evenodd" d="M7 10V7.5a5 5 0 0 1 10 0V10h.5a2.5 2.5 0 0 1 2.5 2.5v6a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 18.5v-6A2.5 2.5 0 0 1 6.5 10H7zm2 0h6V7.5a3 3 0 0 0-6 0V10z" />,
  sun: <><circle cx="12" cy="12" r="4.5" /><path d="M11 1.5h2v3h-2zm0 18h2v3h-2zM1.5 11h3v2h-3zm18 0h3v2h-3z" /></>,
  logout: <path d="M5 3h8v2H5v14h8v2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zm11 4 5 5-5 5-1.4-1.4L17.2 13H9v-2h8.2l-2.6-2.6L16 7z" />,
  receipt: <path fillRule="evenodd" d="M6 2.5h12A1.5 1.5 0 0 1 19.5 4v17.5l-2.7-1.7-2.4 1.7-2.4-1.7-2.4 1.7-2.4-1.7L4.5 21.5V4A1.5 1.5 0 0 1 6 2.5zM8 7.5V9.3h8V7.5H8zm0 3.6v1.8h8v-1.8H8zm0 3.6v1.8h5v-1.8H8z" />,
  flag: <path d="M5 2.5h2V4h11.5l-2 4.5 2 4.5H7v8.5H5v-18z" />,
  inbox: <path fillRule="evenodd" d="M5.5 3.5h13a2 2 0 0 1 1.9 1.4l1.6 5.6V18a2.5 2.5 0 0 1-2.5 2.5h-15A2.5 2.5 0 0 1 2 18v-7.5l1.6-5.6a2 2 0 0 1 1.9-1.4zM5.7 5.7 4.4 10.5H9l.5 2h5l.5-2h4.6l-1.3-4.8H5.7z" />,
  bolt: <path d="M13.5 2 4.5 13.5h6L9.5 22l9-11.5h-6L13.5 2z" />,
};

export type IconName = keyof typeof G;

export function Icon({ name, className, title }: { name: IconName | string; className?: string; title?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden={title ? undefined : true} role={title ? "img" : undefined} aria-label={title}>
      {G[name] ?? G.info}
    </svg>
  );
}

/** iOS-style app-icon tile: squircle, vertical gradient, inner highlight, soft coloured shadow. */
export function Tile({ name, color = "blue", size, className = "" }: { name: IconName | string; color?: string; size?: "xs" | "sm" | "lg" | "xl"; className?: string }) {
  return <span className={`tile c-${color} ${size ?? ""} ${className}`}><Icon name={name} /></span>;
}
