import React from 'react';

// Small, recognizable brand marks for the payment-method chips (landing + billing
// pages). Kept as inline SVG so there's no extra asset/network request.

export const VisaIcon = () => (
  <svg className="pay-icon" viewBox="0 0 48 32" aria-label="Visa">
    <rect width="48" height="32" rx="5" fill="#1A1F71" />
    <text x="24" y="21" textAnchor="middle" fontFamily="Arial, sans-serif" fontSize="13" fontWeight="800" fontStyle="italic" fill="#fff">VISA</text>
  </svg>
);

export const MastercardIcon = () => (
  <svg className="pay-icon" viewBox="0 0 48 32" aria-label="Mastercard">
    <rect width="48" height="32" rx="5" fill="#fff" stroke="#e3ebe5" />
    <circle cx="20" cy="16" r="9" fill="#EB001B" />
    <circle cx="28" cy="16" r="9" fill="#F79E1B" />
    <path d="M24 9.5a9 9 0 0 1 0 13 9 9 0 0 1 0-13z" fill="#FF5F00" />
  </svg>
);

export const PaymeIcon = () => (
  <svg className="pay-icon" viewBox="0 0 32 32" aria-label="Payme">
    <rect width="32" height="32" rx="8" fill="#00CDBA" />
    <path d="M10 22V10h6.2a4.4 4.4 0 0 1 0 8.8H13V22H10zm3-6.2h3a2 2 0 0 0 0-4h-3v4z" fill="#fff" />
  </svg>
);

export const ClickIcon = () => (
  <svg className="pay-icon" viewBox="0 0 32 32" aria-label="Click">
    <rect width="32" height="32" rx="8" fill="#FF7A00" />
    <path d="M21 12.2a5.6 5.6 0 1 0 0 7.6" stroke="#fff" strokeWidth="2.4" fill="none" strokeLinecap="round" />
  </svg>
);

export const CardIcon = () => (
  <svg className="pay-icon" viewBox="0 0 32 32" aria-label="Karta">
    <rect x="3" y="8" width="26" height="16" rx="3" fill="#087b40" />
    <rect x="3" y="12" width="26" height="3.4" fill="#fff" opacity=".85" />
    <rect x="6" y="19" width="8" height="2.2" rx="1" fill="#fff" opacity=".85" />
  </svg>
);
