import { NextRequest, NextResponse } from "next/server"
import { API_HEADERS } from "@/lib/api-headers"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

const ALLOWED_PARAMS = ["limit", "min_risk", "max_risk", "alerted_only", "agency", "q"] as const

export async function GET(req: NextRequest) {
  try {
    const incoming = new URL(req.url).searchParams
    const params = new URLSearchParams()
    for (const key of ALLOWED_PARAMS) {
      const value = incoming.get(key)
      if (value !== null && value !== "") {
        params.set(key, value)
      }
    }
    const qs = params.toString()
    const url = `${API_BASE}/api/analyses${qs ? `?${qs}` : ""}`

    const res = await fetch(url, { headers: API_HEADERS })
    if (!res.ok) {
      return NextResponse.json(
        { error: `Backend returned ${res.status}` },
        { status: 502 }
      )
    }
    const data = await res.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error(error)
    return NextResponse.json([])
  }
}
