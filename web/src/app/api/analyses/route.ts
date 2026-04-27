import { NextRequest, NextResponse } from "next/server"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url)
    const limit = searchParams.get("limit") || "50"
    
    const res = await fetch(`${API_BASE}/api/analyses?limit=${limit}`)
    const data = await res.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error(error)
    return NextResponse.json([])
  }
}