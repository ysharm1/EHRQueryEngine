'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

// Patient Analytics has been merged into the unified Query page ("Advanced" tab).
export default function ClinicalQueryRedirect() {
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
