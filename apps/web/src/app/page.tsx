import { redirect } from 'next/navigation';

/**
 * `/` has no screen of its own — every real destination lives under
 * `(protected)` or `(auth)`. Redirecting to `/dashboard` immediately hands
 * off to `middleware.ts`, which bounces to `/login` when there's no session.
 */
export default function HomePage() {
  redirect('/dashboard');
}
