import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Argusd Dashboard",
  description: "Hour 0–3 dashboard scaffold for Argusd",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
