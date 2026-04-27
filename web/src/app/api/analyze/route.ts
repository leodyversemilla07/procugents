import { NextRequest, NextResponse } from "next/server"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export async function GET() {
  try {
    const res = await fetch(`${API_BASE}/api/stats`, {
      headers: { "Content-Type": "application/json" },
    })
    const data = await res.json()
    return NextResponse.json(data)
  } catch (error) {
    // Return defaults if API not running
    return NextResponse.json({
      total_analyzed: 0,
      anomalies_found: 0,
      active_alerts: 0,
      compliance_rate: 0,
    })
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const { contract_id, contract_description, contract_amount } = body

    const res = await fetch(`${API_BASE}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contract_id,
        contract_description,
        contract_amount,
      }),
    })

    if (!res.ok) {
      throw new Error(`API error: ${res.status}`)
    }

    const data = await res.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error(error)
    return NextResponse.json(
      { error: String(error) },
      { status: 500 }
    )
  }
}