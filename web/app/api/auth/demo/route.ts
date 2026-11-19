import { NextResponse } from "next/server";
import { AUTH_MODE } from "@/lib/server/config";

// Seeded, synthetic demo accounts (scripts/seed.py). Only offered by the dev login.
const ACCOUNTS = [
  { group: "SME", email: "anna.keller@muster-maschinenbau.demo", name: "Anna Keller", org: "Muster Maschinenbau AG", note: "Manufacturing, 48 staff. Has an active application.", icon: "building", color: "blue" },
  { group: "SME", email: "luca.bernasconi@alpina-gastro.demo", name: "Luca Bernasconi", org: "Alpina Gastro GmbH", note: "Hospitality, 22 staff. Works with an accountant.", icon: "building", color: "orange" },
  { group: "SME", email: "mia.stalder@pixelwerk.demo", name: "Mia Stalder", org: "Pixelwerk Studio GmbH", note: "Software, 12 staff. Application still a draft.", icon: "building", color: "purple" },
  { group: "Lender", email: "sandra.huber@regionalbank-zuerich.demo", name: "Sandra Huber", org: "Regionalbank Zürich", note: "Broad criteria, mid-size loans.", icon: "bank", color: "indigo" },
  { group: "Lender", email: "peter.imhof@kantonalbank-bern.demo", name: "Peter Imhof", org: "Kantonalbank Bern", note: "Strict criteria, strong balance sheets.", icon: "bank", color: "teal" },
  { group: "Lender", email: "dana.vogel@helvetia-debt.demo", name: "Dana Vogel", org: "Helvetia Debt Partners", note: "Growth-focused debt fund.", icon: "bank", color: "pink" },
  { group: "Accountant", email: "marco.rossi@treuhand-rossi.demo", name: "Marco Rossi", org: "Treuhand Rossi AG", note: "Prepares applications for clients.", icon: "people", color: "green" },
  { group: "Operator", email: "ops@credsort.demo", name: "CredSort Operations", org: "CredSort", note: "Verifies companies, sets prices.", icon: "shield", color: "gray" },
];
export async function GET() {
  if (AUTH_MODE !== "dev") return NextResponse.json({ detail: "not found" }, { status: 404 });
  return NextResponse.json(ACCOUNTS);
}
