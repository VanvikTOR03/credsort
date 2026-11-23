// Payment brand marks, drawn as simple vector approximations (swap for the provider's official assets in production).
export function Visa({ h = 22 }: { h?: number }) {
  return (
    <svg height={h} viewBox="0 0 64 22" role="img" aria-label="Visa"><rect width="64" height="22" rx="3" fill="#fff" />
      <text x="32" y="17" textAnchor="middle" fontFamily="Arial Black, Arial, sans-serif" fontWeight="900" fontStyle="italic" fontSize="17" fill="#1A1F71" letterSpacing="-.5">VISA</text></svg>
  );
}
export function Mastercard({ h = 22 }: { h?: number }) {
  return (
    <svg height={h} viewBox="0 0 36 22" role="img" aria-label="Mastercard"><rect width="36" height="22" rx="3" fill="#fff" />
      <circle cx="13.5" cy="11" r="7" fill="#EB001B" /><circle cx="22.5" cy="11" r="7" fill="#F79E1B" />
      <path d="M18 5.3a7 7 0 0 1 0 11.4 7 7 0 0 1 0-11.4z" fill="#FF5F00" /></svg>
  );
}
export function Twint({ h = 22 }: { h?: number }) {
  return (
    <svg height={h} viewBox="0 0 60 22" role="img" aria-label="TWINT"><rect width="60" height="22" rx="4" fill="#000" />
      <text x="30" y="15.5" textAnchor="middle" fontFamily="Helvetica, Arial, sans-serif" fontWeight="700" fontSize="12" fill="#fff" letterSpacing="1">TWINT</text></svg>
  );
}
