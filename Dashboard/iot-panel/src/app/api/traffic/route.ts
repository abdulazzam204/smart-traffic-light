import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const response = await fetch("http://127.0.0.1:5000/traffic", {
      cache: "no-store",
    });
    if (!response.ok) {
      return NextResponse.json(
        { error: "traffic server not reachable" },
        { status: 502 }
      );
    }
    const data = await response.json();
    return NextResponse.json(data, {
      headers: {
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    return NextResponse.json(
      { error: "traffic server not reachable" },
      { status: 502 }
    );
  }
}
