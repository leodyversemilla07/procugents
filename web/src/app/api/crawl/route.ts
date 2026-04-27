import { NextRequest, NextResponse } from "next/server"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export async function POST(req: NextRequest) {
  try {
    let agency = ""
    try {
      const body = await req.json()
      agency = body.agency || ""
    } catch {
      // No body, use default
    }

    const url = agency ? `${API_BASE}/api/crawl?agency=${encodeURIComponent(agency)}` : `${API_BASE}/api/crawl`
    
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    })

    if (!res.ok) {
      throw new Error(`API error: ${res.status}`)
    }

    const data = await res.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error(error)
    return NextResponse.json(
      { error: String(error), analyzed: 0 },
      { status: 500 }
    )
  }
}