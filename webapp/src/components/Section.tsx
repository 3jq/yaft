import { ReactNode } from "react";
export function Hr() { return <div className="hr" />; }
export function Section({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`px-5 py-5 ${className}`}>{children}</section>;
}
