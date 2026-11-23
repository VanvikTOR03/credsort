import { NextResponse } from "next/server";
import { AUTH_MODE } from "@/lib/server/config";

// Seeded, synthetic demo accounts (scripts/seed.py). Only offered by the dev login.
const ACCOUNTS = [
  { group: "SME", email: "anna.keller@muster-maschinenbau.demo", name: "Anna Keller", org: "Muster Maschinenbau AG", icon: "building" },
  { group: "SME", email: "luca.bernasconi@alpina-gastro.demo", name: "Luca Bernasconi", org: "Alpina Gastro GmbH", icon: "building" },
  { group: "SME", email: "mia.stalder@pixelwerk.demo", name: "Mia Stalder", org: "Pixelwerk Studio GmbH", icon: "building" },
  { group: "Lender", email: "sandra.huber@regionalbank-zuerich.demo", name: "Sandra Huber", org: "Regionalbank Zürich", icon: "bank" },
  { group: "Lender", email: "peter.imhof@kantonalbank-bern.demo", name: "Peter Imhof", org: "Kantonalbank Bern", icon: "bank" },
  { group: "Lender", email: "dana.vogel@helvetia-debt.demo", name: "Dana Vogel", org: "Helvetia Debt Partners", icon: "bank" },
  { group: "Accountant", email: "marco.rossi@treuhand-rossi.demo", name: "Marco Rossi", org: "Treuhand Rossi AG", icon: "people" },
  { group: "Operator", email: "ops@credsort.demo", name: "CredSort Operations", org: "CredSort", icon: "shield" },
];
export async function GET() {
  if (AUTH_MODE !== "dev") return NextResponse.json({ detail: "not found" }, { status: 404 });
  return NextResponse.json(ACCOUNTS);
}
