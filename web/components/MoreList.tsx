"use client";
import React, { useState } from "react";
import { api, useApi } from "@/lib/client/api";
import { Button, ErrorNote, List, PageHeader, Pill, Row, Section, Sheet } from "./ui";
import { useSession } from "./Providers";

export function MorePage({ extra, danger }: { extra?: React.ReactNode; danger?: boolean }) {
  const { session } = useSession();
  const s = session!;
  const unread = useApi<{ unread: number }>("notification", "/v1/notifications");
  const [del, setDel] = useState(false), [err, setErr] = useState<any>(null), [sent, setSent] = useState(false);
  async function signOut() { await fetch("/api/auth/logout", { method: "POST" }); location.href = "/login"; }
  async function requestDelete() { setErr(null); try { await api("identity", "/v1/organizations/current/deletion-request", { method: "POST" }); setSent(true); } catch (e: any) { setErr(e); } }
  return (
    <div className="stack-l">
      <PageHeader title="More" subtitle={`${s.user.name} · ${s.org.name}`} />
      {extra}
      <Section title="General">
        <List>
          <Row icon="bell" color="red" title="Notifications" href="/notifications" value={unread.data?.unread ? <Pill tone="red">{unread.data.unread}</Pill> : undefined} />
          <Row icon="building" color="gray" title="Organization" sub={s.org.name} value={<Pill tone={s.org.kyb_status === "VERIFIED" ? "green" : "orange"}>{s.org.kyb_status === "VERIFIED" ? "Verified" : s.org.kyb_status.toLowerCase()}</Pill>} />
        </List>
      </Section>
      <Section title="Account" footer="Demo mode: this build signs you in with a demo profile instead of a password.">
        <List>
          <Row icon="logout" color="gray" title="Sign out" onClick={signOut} />
          {danger && <Row icon="trash" color="red" title="Delete my data" sub="Ask us to erase your organization" onClick={() => setDel(true)} />}
        </List>
      </Section>
      <Sheet open={del} onClose={() => setDel(false)} title={sent ? "Request received" : "Delete your data?"}>
        <div className="stack">{sent ? <p>We started the deletion. Your data is removed from every part of CredSort. Some records must be kept by law and are anonymized instead.</p> : <>
          <p>This removes your organization, your numbers and your requests from every part of CredSort. It cannot be undone. Records we must keep by law are anonymized.</p><ErrorNote error={err} />
          <Button block variant="danger" onClick={requestDelete}>Delete everything</Button></>}
          <Button block variant="plain" onClick={() => setDel(false)}>{sent ? "Close" : "Cancel"}</Button></div>
      </Sheet>
    </div>
  );
}
