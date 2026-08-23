'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

// Query Builder has been merged into the unified Query page ("Ask" tab).
export default function QueryBuilderRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace('/query');
  }, [router]);
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="text-lg text-gray-500">Redirecting to Query…</div>
    </div>
  );
}
