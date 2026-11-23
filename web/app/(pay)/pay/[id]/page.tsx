"use client";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { api, useApi } from "@/lib/client/api";
import { Icon, Logo } from "@/components/Icon";
import { Mastercard, Twint, Visa } from "@/components/Brands";
import { useSession } from "@/components/Providers";
import { chf } from "@/lib/format";

type Tab = "card" | "twint";
const luhn = (n: string) => { let s = 0, alt = false; for (let i = n.length - 1; i >= 0; i--) { let d = +n[i]; if (alt) { d *= 2; if (d > 9) d -= 9; } s += d; alt = !alt; } return n.length >= 13 && s % 10 === 0; };
const brandOf = (n: string): "VISA" | "MASTERCARD" | null => (/^4/.test(n) ? "VISA" : /^(5[1-5]|2[2-7])/.test(n) ? "MASTERCARD" : null);
const groupCard = (v: string) => v.replace(/\D/g, "").slice(0, 16).replace(/(.{4})/g, "$1 ").trim();
const groupExp = (v: string) => { const d = v.replace(/\D/g, "").slice(0, 4); return d.length > 2 ? `${d.slice(0, 2)} / ${d.slice(2)}` : d; };

/** Pseudo QR code for the demo (not scannable). A real TWINT flow shows the provider's code. */
function Qr({ seed }: { seed: string }) {
  const cells = useMemo(() => {
    let x = [...seed].reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 7), N = 25;
    const rnd = () => ((x = (x * 1664525 + 1013904223) >>> 0) / 2 ** 32);
    const out: [number, number][] = [];
    const finder = (r: number, c: number) => (r < 8 && c < 8) || (r < 8 && c >= N - 8) || (r >= N - 8 && c < 8);
    for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) if (!finder(r, c) && rnd() > 0.52) out.push([r, c]);
    return out;
  }, [seed]);
  const N = 25;
  const eye = (r: number, c: number) => <g key={`${r}${c}`}><rect x={c} y={r} width="7" height="7" fill="#020C23" /><rect x={c + 1} y={r + 1} width="5" height="5" fill="#fff" /><rect x={c + 2} y={r + 2} width="3" height="3" fill="#020C23" /></g>;
  return <svg className="qr" viewBox={`-1 -1 ${N + 2} ${N + 2}`} role="img" aria-label="TWINT QR code (demo)">{cells.map(([r, c]) => <rect key={`${r}-${c}`} x={c} y={r} width="1" height="1" fill="#020C23" />)}{eye(0, 0)}{eye(0, N - 7)}{eye(N - 7, 0)}</svg>;
}

function Checkout() {
  const { id } = useParams<{ id: string }>();
  const back = useSearchParams().get("return") === "1";
  const { session } = useSession();
  const price = useApi<any>("billing", "/v1/unlock/price");
  const [tab, setTab] = useState<Tab>("card");
  // Demo values (the standard test card); card details never leave this page.
  const [num, setNum] = useState("4242 4242 4242 4242"), [exp, setExp] = useState("12 / 34"), [cvc, setCvc] = useState("123"), [holder, setHolder] = useState(session?.user.name ?? "");
  const [phase, setPhase] = useState<"form" | "processing" | "done">("form"), [err, setErr] = useState(""), [ref, setRef] = useState("");
  const amount = price.data?.status === "PRICED" ? chf(price.data.amount, { decimals: 2 }) : "";
  const digits = num.replace(/\D/g, ""), brand = brandOf(digits);
  const errors = useMemo(() => {
    const e: Record<string, string> = {};
    if (!luhn(digits) || !brand) e.num = "Enter a valid Visa or Mastercard number";
    const m = /^(\d{2}) \/ (\d{2})$/.exec(exp);
    if (!m || +m[1] < 1 || +m[1] > 12 || +m[2] + 2000 < new Date().getFullYear() || (+m[2] + 2000 === new Date().getFullYear() && +m[1] < new Date().getMonth() + 1)) e.exp = "Check the date";
    if (!/^\d{3}$/.test(cvc)) e.cvc = "3 digits";
    if (holder.trim().length < 2) e.holder = "Required";
    return e;
  }, [digits, brand, exp, cvc, holder]);
  const [touched, setTouched] = useState(false);

  useEffect(() => {
    if (phase !== "done") return;
    const t = setTimeout(() => {
      if (window.opener && !back) { window.opener.postMessage({ type: "credsort:paid" }, location.origin); window.close(); }
      else location.href = `/sme/loans/${id}`;
    }, 2200);
    return () => clearTimeout(t);
  }, [phase, back, id]);

  async function pay(method: "VISA" | "MASTERCARD" | "TWINT") {
    setErr(""); setPhase("processing");
    try {
      await new Promise((r) => setTimeout(r, 1600)); // issuer authorisation (demo)
      const r = await api("billing", "/v1/unlock/payments", { method: "POST", body: { application_id: id, method } });
      setRef(r.provider_ref); setPhase("done");
    } catch (e: any) { setErr(e.detail ?? "The payment could not be completed."); setPhase("form"); }
  }
  function submitCard(e: React.FormEvent) { e.preventDefault(); setTouched(true); if (Object.keys(errors).length || !brand) return; pay(brand); }

  if (phase === "done") {
    return (
      <div className="pay-page"><div className="pay-box"><div className="pay-card"><div className="pay-done">
        <div className="pay-ok"><svg className="check-draw" width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg></div>
        <h1 className="t-title">Payment successful</h1>
        <div className="num t-large">{amount}</div>
        <p className="t-foot">Reference {ref}</p>
        <p className="t-foot">Returning to CredSort</p>
      </div></div></div></div>
    );
  }

  return (
    <div className="pay-page">
      <div className="pay-box">
        <div className="hstack spread"><Logo /><span className="secure"><Icon name="lock" />Secure checkout</span></div>
        <form className="pay-card" onSubmit={submitCard} noValidate>
          <div className="stack-s"><span className="t-over">CredSort unlock fee</span><div className="num t-large">{amount || <span className="skel" style={{ display: "inline-block", width: 120, height: 34 }} />}</div></div>
          <div className="pay-tabs" role="tablist" aria-label="Payment method">
            <button type="button" role="tab" aria-selected={tab === "card"} onClick={() => setTab("card")}><span className="logos"><Visa h={20} /><Mastercard h={20} /></span></button>
            <button type="button" role="tab" aria-selected={tab === "twint"} onClick={() => setTab("twint")}><Twint h={20} /></button>
          </div>

          {tab === "card" ? (
            <>
              <div><label className="lbl" htmlFor="cc">Card number</label>
                <div className="card-field"><input id="cc" className={`in ${touched && errors.num ? "err" : ""}`} inputMode="numeric" autoComplete="cc-number" value={num} onChange={(e) => setNum(groupCard(e.target.value))} placeholder="1234 1234 1234 1234" />
                  <span className="brand">{brand === "VISA" ? <Visa h={20} /> : brand === "MASTERCARD" ? <Mastercard h={20} /> : null}</span></div>
                {touched && errors.num && <p className="field-error">{errors.num}</p>}</div>
              <div className="cols-2">
                <div><label className="lbl" htmlFor="ex">Expiry</label><input id="ex" className={`in ${touched && errors.exp ? "err" : ""}`} inputMode="numeric" autoComplete="cc-exp" value={exp} onChange={(e) => setExp(groupExp(e.target.value))} placeholder="MM / YY" />{touched && errors.exp && <p className="field-error">{errors.exp}</p>}</div>
                <div><label className="lbl" htmlFor="cv">CVC</label><input id="cv" className={`in ${touched && errors.cvc ? "err" : ""}`} inputMode="numeric" autoComplete="cc-csc" value={cvc} onChange={(e) => setCvc(e.target.value.replace(/\D/g, "").slice(0, 3))} placeholder="123" />{touched && errors.cvc && <p className="field-error">{errors.cvc}</p>}</div>
              </div>
              <div><label className="lbl" htmlFor="ch">Name on card</label><input id="ch" className={`in ${touched && errors.holder ? "err" : ""}`} autoComplete="cc-name" value={holder} onChange={(e) => setHolder(e.target.value)} />{touched && errors.holder && <p className="field-error">{errors.holder}</p>}</div>
              {err && <p className="field-error" role="alert">{err}</p>}
              <button className="btn block" type="submit" disabled={phase === "processing" || !amount}>{phase === "processing" ? <><span className="spinner" />Processing</> : `Pay ${amount}`}</button>
            </>
          ) : (
            <>
              <Qr seed={id} />
              <p className="center t-foot">Scan with the TWINT app</p>
              {err && <p className="field-error center" role="alert">{err}</p>}
              <button type="button" className="btn block" onClick={() => pay("TWINT")} disabled={phase === "processing" || !amount}>{phase === "processing" ? <><span className="spinner" />Waiting for TWINT</> : "Confirm in TWINT"}</button>
            </>
          )}
          <p className="t-cap center">Demo checkout. No money is charged and card details are not sent or stored.</p>
        </form>
      </div>
    </div>
  );
}
export default function Pay() { return <Suspense><Checkout /></Suspense>; }
