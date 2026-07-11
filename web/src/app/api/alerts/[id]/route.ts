import { NextRequest, NextResponse } from "next/server"
import { API_HEADERS } from "@/lib/api-headers"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const { id } = await params
    const body = await req.json()
    const res = await fetch(`${API_BASE}/api/alerts/${id}`, {
      method: "PATCH",
      headers: API_HEADERS,
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const text = await res.text()
      return NextResponse.json({ error: text }, { status: res.status })
    }
    const data = await res.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error(error)
    return NextResponse.json({ error: "Failed to update alert" }, { status: 500 })
  }
}
