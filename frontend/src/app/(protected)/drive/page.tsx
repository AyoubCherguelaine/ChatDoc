"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function DrivePage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/advanced-ocr");
  }, [router]);

  return null;
}
