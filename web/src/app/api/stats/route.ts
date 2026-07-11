import { NextResponse } from "next/server"
import { API_HEADERS } from "@/lib/api-headers"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export async function GET() {
  try {
    const res = await fetch(`${API_BASE}/api/stats`, {
      headers: API_HEADERS,
    })
    const data = await res.json()
    return NextResponse.json(data)
  } catch {
    return NextResponse.json({
      total_analyzed: 0,
      anomalies_found: 0,
      active_alerts: 0,
      compliance_rate: 0,
    })
  }
}