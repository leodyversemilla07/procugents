import { NextResponse } from "next/server"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export async function GET() {
  try {
    const res = await fetch(`${API_BASE}/api/stats`)
    const data = await res.json()
    return NextResponse.json(data)
  } catch (error) {
    return NextResponse.json({
      total_analyzed: 0,
      anomalies_found: 0,
      active_alerts: 0,
      compliance_rate: 0,
    })
  }
}