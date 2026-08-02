(function (root) {
  const TMT_VERTICALS = Object.freeze([
    'AI/Cloud/Semiconductor Infrastructure','Enterprise Software','Data/Analytics','Cybersecurity/Identity',
    'Fintech/Payments/Insurtech','Commerce/Marketplaces','Consumer Internet/Media/Gaming','Digital Health',
    'Climate/Industrial Tech','Space/Communications','Robotics/Mobility','Other'
  ]);
  root.tmtTaxonomy = { TMT_VERTICALS };
})(typeof window === 'undefined' ? globalThis : window);
