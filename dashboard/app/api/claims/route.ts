import { NextResponse } from "next/server";

import { readClaims } from "../../../lib/claims";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export function GET() {
  return NextResponse.json(readClaims(), {
    headers: { "Cache-Control": "no-store, max-age=0" },
  });
}
