"use client";
import { MorePage } from "@/components/MoreList";
import { List, Row, Section } from "@/components/ui";
import { useSession } from "@/components/Providers";

export default function SmeMore() {
  const { session } = useSession();
  return <MorePage danger={!session!.actingFor} extra={<Section title="Your company"><List>
    <Row icon="receipt" color="green" title="Fees" sub="One-off CHF 190 per request" href="/sme/fees" />
    {!session!.actingFor && <Row icon="people" color="accent" title="Accountant" sub="Give your fiduciary access" href="/sme/accountant" />}
  </List></Section>} />;
}
