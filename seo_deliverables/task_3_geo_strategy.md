# Task 3: AI Search Optimization (GEO) Strategy

This document outlines the Generative Engine Optimization (GEO) strategy for Common Notary Apostille (CNA) to achieve high visibility in AI search engine results.

## 1. Citation and Directory Building

To be recognized by AI search engines, CNA must have a consistent and accurate presence across a wide range of online directories and citation sources. The following is a prioritized list of platforms where CNA should be listed. For each, the exact URL and submission instructions should be followed.

### High-Priority Directories

| Directory | URL | Submission Instructions |
|---|---|---|
| Google Business Profile | [google.com/business](https://google.com/business) | Claim and fully optimize the existing profile. Ensure all information is 100% accurate and complete. |
| Yelp | [biz.yelp.com](https://biz.yelp.com) | Claim and complete the business profile. Respond to all reviews. |
| Bing Places | [bingplaces.com](https://www.bingplaces.com/) | Create a new listing or claim an existing one. |
| Apple Maps | [mapsconnect.apple.com](https://mapsconnect.apple.com/) | Add or update your business information. |

### Legal-Specific Directories

| Directory | URL | Submission Instructions |
|---|---|---|
| Avvo | [avvo.com](https://www.avvo.com/for-lawyers) | Claim or create a profile. Focus on completing the profile with detailed information about services. |
| FindLaw | [lawyermarketing.com/our-products/legal-directory/](https://www.lawyermarketing.com/our-products/legal-directory/) | Submit a profile to be included in their directory. |
| Justia | [justia.com/lawyers](https://www.justia.com/lawyers) | Create a free profile and ensure it is complete. |
| Martindale-Hubbell | [martindale.com](https://www.martindale.com/marketyourfirm/) | Create a professional profile. |

### Notary-Specific Directories

| Directory | URL | Submission Instructions |
|---|---|---|
| National Notary Association (NNA) | [nationalnotary.org](https://www.nationalnotary.org/my-nna/my-signing-agent-profile) | If the founder is a member, ensure the profile is complete and up-to-date. |
| 123Notary | [123notary.com](https://www.123notary.com/) | Create a listing. |
| Notary Rotary | [notaryrotary.com](https://www.notaryrotary.com/) | Create a listing. |
| Snapdocs | [snapdocs.com/notaries](https://www.snapdocs.com/notaries) | Create a profile to be listed as a signing agent. |

## 2. Schema Markup

To help AI engines understand the content and services of CNA, the following JSON-LD schema markup should be added to the website. This code should be placed in the `<head>` section of the HTML on the relevant pages.

### LocalBusiness and LegalService Schema

This schema should be placed on the homepage and all service pages.

```json
{
  "@context": "https://schema.org",
  "@type": "LegalService",
  "name": "Common Notary Apostille",
  "description": "Premier legal support services firm in Washington D.C., specializing in apostille authentication, estate document notarization, and digital deposition services.",
  "url": "https://commonapostille.com",
  "telephone": "+1-202-803-7203",
  "email": "admin@commonapostille.com",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "1901 Pennsylvania Ave NW, Suite 900",
    "addressLocality": "Washington",
    "addressRegion": "D.C.",
    "postalCode": "20006",
    "addressCountry": "US"
  },
  "geo": {
    "@type": "GeoCoordinates",
    "latitude": "38.900490",
    "longitude": "-77.043180"
  },
  "founder": {
    "@type": "Person",
    "name": "Byron Hamlar"
  },
  "foundingDate": "2019-03-25",
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "5.0",
    "reviewCount": "64"
  },
  "areaServed": [
    {
      "@type": "City",
      "name": "Washington D.C."
    },
    {
      "@type": "State",
      "name": "Virginia"
    },
    {
      "@type": "State",
      "name": "Maryland"
    }
  ],
  "hasOfferCatalog": {
    "@type": "OfferCatalog",
    "name": "Legal Support Services",
    "itemListElement": [
      {
        "@type": "Offer",
        "itemOffered": {
          "@type": "Service",
          "name": "Apostille Authentication"
        }
      },
      {
        "@type": "Offer",
        "itemOffered": {
          "@type": "Service",
          "name": "Estate Document Notarization"
        }
      },
      {
        "@type": "Offer",
        "itemOffered": {
          "@type": "Service",
          "name": "Digital Deposition Services"
        }
      }
    ]
  }
}
```

### FAQPage Schema

This schema should be placed on the FAQ page.

```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "What is an apostille?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "An apostille is a certificate that authenticates the origin of a public document (e.g., a birth, marriage, or death certificate, a judgment, an extract of a register, or a notarial attestation). Apostilles can only be issued for documents issued in one country party to the Apostille Convention and that are to be used in another country which is also a party to the Convention."
      }
    },
    {
      "@type": "Question",
      "name": "How long does the apostille process take?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Processing times vary by state and document type. We offer same-day service in Washington, D.C., and expedited services for other jurisdictions. Contact us for a specific timeline for your documents."
      }
    }
  ]
}
```

### BreadcrumbList Schema

This schema should be implemented on all pages except the homepage to help users and search engines understand the website's structure.

```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {
      "@type": "ListItem",
      "position": 1,
      "name": "Home",
      "item": "https://commonapostille.com"
    },
    {
      "@type": "ListItem",
      "position": 2,
      "name": "Services",
      "item": "https://commonapostille.com/services"
    },
    {
      "@type": "ListItem",
      "position": 3,
      "name": "Apostille",
      "item": "https://commonapostille.com/services/apostille"
    }
  ]
}
```
## 3. Content Strategy for AI Recognition

To be cited by AI engines, CNA's content must be authoritative, easily digestible, and directly answer the questions users are asking. The following content strategy will help CNA achieve this.

### Content Principles

*   **Answer-First Content:** Structure content to provide direct answers to common questions at the beginning of each section. Use clear headings (H1, H2, H3) to organize content logically.
*   **Use Structured Data:** Employ bullet points, numbered lists, and tables to present information in a scannable format that AI can easily parse and extract.
*   **Demonstrate E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness):**
    *   **Experience:** Share case studies and real-world examples of apostille and notarization work.
    *   **Expertise:** Create detailed guides and articles on complex topics like "Apostille vs. Embassy Legalization."
    *   **Authoritativeness:** Include author bios with credentials and feature expert quotes.
    *   **Trustworthiness:** Cite sources for all statistics and claims.
*   **Maintain Recency:** Regularly update content (at least quarterly) to ensure it is current. AI models have a recency bias and favor fresh information.

### Content Publishing Plan

*   **Website:** Publish detailed service pages, location pages, and blog posts that address specific user queries. The blog content calendar in Task 2 will provide a roadmap for this.
*   **Google Business Profile:** Regularly publish Google Posts to highlight services, share updates, and answer common questions. The 52 weekly Google Post templates in Task 4 will support this.
*   **Press Releases:** Distribute press releases for significant company news, such as the expansion into the Richmond market, to generate authoritative backlinks and mentions.
*   **Legal Directories:** Ensure profiles on legal directories like Avvo and Justia are complete and link back to the CNA website.

## 4. Authority Signals

AI engines use authority signals to determine which businesses to recommend. The following actions will help build CNA's digital authority:

*   **Backlink Acquisition:** Obtain backlinks from reputable websites, including legal blogs, news outlets, and professional associations. Guest posting on relevant blogs can be an effective strategy.
*   **Press Release Distribution:** Use a press release distribution service to announce company news, such as market expansions or new service offerings. This can generate high-authority backlinks and brand mentions.
*   **Professional Association Listings:** Ensure CNA is listed in the directories of all relevant professional associations, such as the National Notary Association and local bar associations.
*   **Unlinked Brand Mentions:** Encourage brand mentions on platforms that AI engines frequently reference, such as Reddit and Quora. Participating in relevant discussions and providing helpful answers can increase brand visibility.

## 5. Review Strategy

A consistent stream of positive reviews is a powerful trust signal for AI engines. The following system will help CNA generate more reviews on Google and other third-party platforms.

### Review Generation System

1.  **Identify Satisfied Clients:** After a service is completed, identify clients who have had a positive experience.
2.  **Send a Personalized Email:** Send a personalized email thanking the client for their business and requesting a review. The email should include a direct link to the Google review page.
3.  **Follow Up:** If the client does not leave a review within a week, send a polite follow-up email.

### Review Request Email Template

**Subject: A Quick Favor for Common Notary Apostille**

Dear [Client Name],

Thank you for choosing Common Notary Apostille for your [Service Provided] needs. We appreciate your trust in our services.

Would you be willing to take a moment to share your experience with us on Google? Your feedback helps us improve and allows others to learn about our commitment to precision and professionalism.

[Link to Google Review Page]

Thank you for your time and for being a valued client.

Sincerely,

The Common Notary Apostille Team
