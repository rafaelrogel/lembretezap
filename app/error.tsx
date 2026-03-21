"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="mx-auto flex min-h-[40vh] max-w-lg flex-col items-center justify-center gap-4 px-6 py-16 text-center">
      <h2 className="text-lg font-semibold text-[var(--Text-900,#212121)]">
        Algo deu errado ao carregar esta página
      </h2>
      <p className="text-sm text-[var(--Text-600,#797781)]">
        Pare o servidor (Ctrl+C) e suba de novo com{" "}
        <code className="rounded bg-neutral-100 px-1.5 py-0.5 text-xs">
          npm run dev
        </code>{" "}
        (já limpa o cache). Se ainda falhar, use{" "}
        <code className="rounded bg-neutral-100 px-1.5 py-0.5 text-xs">
          npm run dev:fix
        </code>
        .
      </p>
      <button
        type="button"
        onClick={() => reset()}
        className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700"
      >
        Tentar de novo
      </button>
    </div>
  );
}
