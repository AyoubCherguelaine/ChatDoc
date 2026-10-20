"use client";

import Image from "next/image";
import { type ImgHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Avatar({
  size = 9,
  src,
  alt = "",
  fallback,
}: Omit<ImgHTMLAttributes<HTMLImageElement>, "src"> & {
  src?: string;
  size?: number;
  fallback?: string;
}) {
  const pixels = size * 4;
  return (
    <div
      className={cn("relative inline-block rounded-full bg-zinc-200")}
      style={{ width: pixels, height: pixels }}
    >
      {src ? (
        <Image
          width={pixels}
          height={pixels}
          unoptimized
          className="rounded-full object-cover"
          src={src}
          alt={alt}
        />
      ) : (
        <span className="flex h-full w-full items-center justify-center text-xs font-medium">
          {fallback ?? "U"}
        </span>
      )}
    </div>
  );
}
