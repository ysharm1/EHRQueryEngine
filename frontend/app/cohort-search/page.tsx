'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

// Cohort Search has been removed from the primary navigation to simplify the
// product flow. This route redirects to the unified Query page.
export default function CohortSearchRedirect() {
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
