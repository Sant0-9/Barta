import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "Barta - AI News Assistant",
  description: "Your intelligent news companion",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>
        {children}
      </body>
    </html>
  )
}