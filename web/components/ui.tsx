"use client";
import Link from "next/link";
import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Icon, Tile } from "./Icon";

export function Button({ children, onClick, variant, size, block, loading, disabled, href, type, label, icon }:
  { children?: React.ReactNode; onClick?: () => void | Promise<void>; variant?: "secondary" | "plain" | "danger" | "danger-soft"; size?: "sm"; block?: boolean; loading?: boolean; disabled?: boolean; href?: string; type?: "submit" | "button"; label?: string; icon?: string }) {
  const [busy, setBusy] = useState(false);
  const cls = ["btn", variant === "danger-soft" ? "danger secondary" : variant, size, block ? "block" : ""].filter(Boolean).join(" ");
  const inner = <>{(loading || busy) ? <span className="spinner" /> : icon ? <Icon name={icon} className="" /> : null}{children}</>;
  if (href) return <Link className={cls} href={href} aria-label={label}>{inner}</Link>;
  return (
    <button className={cls} type={type ?? "button"} disabled={disabled || loading || busy} aria-label={label}
      onClick={async () => { if (!onClick) return; const r = onClick(); if (r && typeof (r as Promise<void>).then === "function") { setBusy(true); try { await r; } finally { setBusy(false); } } }}>
      {inner}
    </button>
  );
}
(Button as any).displayName = "Button";

export const Card = ({ children, className = "", lift, style, flush }: { children: React.ReactNode; className?: string; lift?: boolean; style?: React.CSSProperties; flush?: boolean }) =>
  <div className={`card ${lift ? "lift" : ""} ${flush ? "flush" : ""} ${className}`} style={style}>{children}</div>;

export function Section({ title, footer, children, action }: { title?: string; footer?: React.ReactNode; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <section>
      {title && <div className="section-title hstack spread"><h2 className="t-over">{title}</h2>{action}</div>}
      {children}
      {footer && <p className="t-foot section-foot">{footer}</p>}
    </section>
  );
}

export const List = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => <div className={`list ${className}`}>{children}</div>;

export function Row({ icon, color, title, sub, value, href, onClick, chevron, children, noicon, style, ariaLabel }:
  { icon?: string; color?: string; title: React.ReactNode; sub?: React.ReactNode; value?: React.ReactNode; href?: string; onClick?: () => void; chevron?: boolean; children?: React.ReactNode; noicon?: boolean; style?: React.CSSProperties; ariaLabel?: string }) {
  const body = (
    <>
      {icon && <Tile name={icon} color={color} />}
      <div className="grow"><div className="title">{title}</div>{sub && <div className="sub">{sub}</div>}</div>
      {value !== undefined && <div className="val">{value}</div>}
      {children}
      {(chevron ?? (!!href || !!onClick)) && <Icon name="chevron" className="chev" />}
    </>
  );
  const cls = `row ${noicon || !icon ? "noicon" : ""}`;
  if (href) return <Link href={href} className={cls} style={style} aria-label={ariaLabel}>{body}</Link>;
  if (onClick) return <button className={cls} onClick={onClick} style={style} aria-label={ariaLabel}>{body}</button>;
  return <div className={cls} style={style}>{body}</div>;
}

export function Pill({ children, tone }: { children: React.ReactNode; tone?: "green" | "orange" | "red" | "blue" | "accent" }) {
  return <span className={`pill ${tone ?? ""}`}>{children}</span>;
}

/** iOS-style segmented control: pill track, white thumb with a shadow that slides to the chosen option. */
export function Seg<T extends string>({ options, value, onChange, label, full }: { options: { value: T; label: string }[]; value: T; onChange: (v: T) => void; label: string; full?: boolean }) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const [thumb, setThumb] = useState({ left: 3, width: 0 });
  const [ready, setReady] = useState(false); // no slide on first paint, only when the user switches
  const measure = () => { const el = refs.current[value]; if (el) setThumb({ left: el.offsetLeft, width: el.offsetWidth }); };
  useLayoutEffect(() => { measure(); const t = requestAnimationFrame(() => setReady(true)); return () => cancelAnimationFrame(t); }, [value, options.length]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { window.addEventListener("resize", measure); return () => window.removeEventListener("resize", measure); }); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className={`seg ${full ? "full" : ""}`} role="tablist" aria-label={label}>
      <span className="thumb" style={{ ...thumb, transition: ready ? undefined : "none" }} />
      {options.map((o) => (
        <button key={o.value} type="button" ref={(el) => { refs.current[o.value] = el; }} role="tab" aria-selected={o.value === value} onClick={() => onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  );
}

export function Switch({ checked, onChange, label, disabled }: { checked: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) {
  return <button className="switch" role="switch" aria-checked={checked} aria-label={label} disabled={disabled} onClick={() => onChange(!checked)} />;
}

export function Sheet({ open, onClose, title, children }: { open: boolean; onClose: () => void; title?: string; children: React.ReactNode }) {
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k); document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", k); document.body.style.overflow = ""; };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sheet" role="dialog" aria-modal="true" aria-label={title}>
        <div className="grabber" />
        {title && <h2 className="t-title" style={{ marginBottom: 14 }}>{title}</h2>}
        {children}
      </div>
    </div>
  );
}

export const Skeleton = ({ h = 16, w = "100%", r }: { h?: number; w?: number | string; r?: number }) => <div className="skel" style={{ height: h, width: w, borderRadius: r }} />;
export function ListSkeleton({ rows = 3 }: { rows?: number }) {
  return <List>{Array.from({ length: rows }).map((_, i) => <div className="row" key={i}><div className="skel" style={{ width: 40, height: 40, borderRadius: "27%" }} /><div className="grow stack-s"><Skeleton w="55%" /><Skeleton h={12} w="35%" /></div></div>)}</List>;
}

export function Ring({ value, max = 100, size = 132, stroke = 12, color = "var(--accent)", children }: { value: number; max?: number; size?: number; stroke?: number; color?: string; children?: React.ReactNode }) {
  const [v, setV] = useState(0);
  useEffect(() => { const t = requestAnimationFrame(() => setV(value)); return () => cancelAnimationFrame(t); }, [value]);
  const r = (size - stroke) / 2, c = 2 * Math.PI * r;
  return (
    <div className="ring" style={{ width: size, height: size }}>
      <svg width={size} height={size} aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--fill)" strokeWidth={stroke} />
        <circle className="fg" cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke} strokeDasharray={c} strokeDashoffset={c * (1 - Math.min(v, max) / max)} />
      </svg>
      <div className="ring-c">{children}</div>
    </div>
  );
}

export function Meter({ value, max = 100, label }: { value: number; max?: number; label?: string }) {
  const [w, setW] = useState(0);
  useEffect(() => { const t = requestAnimationFrame(() => setW((value / max) * 100)); return () => cancelAnimationFrame(t); }, [value, max]);
  return <div className="meter" role="progressbar" aria-valuenow={value} aria-valuemax={max} aria-label={label}><i style={{ width: `${w}%` }} /></div>;
}

export function Empty({ icon, color = "gray", title, text, action }: { icon: string; color?: string; title: string; text?: string; action?: React.ReactNode }) {
  return <div className="empty"><Tile name={icon} color={color} size="xl" /><h3 className="t-head">{title}</h3>{text && <p className="muted">{text}</p>}{action}</div>;
}

export function ErrorNote({ error, retry }: { error: { detail: string } | null; retry?: () => void }) {
  if (!error) return null;
  return <div className="banner" role="alert"><Tile name="warning" color="orange" size="sm" /><div className="grow">{error.detail}</div>{retry && <Button size="sm" variant="secondary" onClick={retry}>Retry</Button>}</div>;
}

export function Field({ label, hint, children, error }: { label: string; hint?: string; children: React.ReactNode; error?: string }) {
  return <label className={`field ${error ? "error" : ""}`}><span style={{ flex: "0 0 38%" }}>{label}{hint && <span className="hint" style={{ display: "block" }}>{hint}</span>}</span>{children}</label>;
}

export function Steps({ total, current }: { total: number; current: number }) {
  return <div className="steps" role="progressbar" aria-valuenow={current + 1} aria-valuemax={total} aria-label="Progress">{Array.from({ length: total }).map((_, i) => <i key={i} className={i <= current ? "on" : ""} />)}</div>;
}

export function Success({ title, text, children }: { title: string; text?: string; children?: React.ReactNode }) {
  return (
    <div className="empty">
      <span className="tile xl c-green success-burst"><svg className="check-draw" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg></span>
      <h2 className="t-title">{title}</h2>{text && <p className="muted">{text}</p>}{children}
    </div>
  );
}

/** Plain title row. Back link above, actions on the right. Only dynamic (non-string) subtitles are shown: no marketing copy. */
export function PageHeader({ title, subtitle, back, actions }: { title: string; subtitle?: React.ReactNode; back?: string; actions?: React.ReactNode }) {
  return (
    <div className="title-row">
      <div>
        {back && <Link href={back} className="back"><Icon name="back" />Back</Link>}
        <h1>{title}</h1>
        {subtitle && typeof subtitle !== "string" && <div className="sub">{subtitle}</div>}
      </div>
      {actions && <div className="hstack">{actions}</div>}
    </div>
  );
}
