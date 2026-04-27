import { NextRequest, NextResponse } from "next/server"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    const res = await fetch(`${API_BASE}/api/analyses/${id}`)
    
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