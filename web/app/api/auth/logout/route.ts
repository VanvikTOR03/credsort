import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { COOKIE_NAME } from "@/lib/server/config";
import { destroySession } from "@/lib/server/session";

export async function POST() {
  const id = cookies().get(COOKIE_NAME)?.value;
  if (id) destroySession(id);
  const res = NextResponse.json({ ok: true });
  res.cookies.delete(COOKIE_NAME);
  return res;
}
