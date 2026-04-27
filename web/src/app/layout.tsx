import { Metadata } from "next"

export const metadata: Metadata = {
  title: "RedFlag Agents PH",
  description: "Philippine Government Procurement Anomaly Detection",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}