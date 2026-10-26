"""
Bilingual (English & Arabic) Intelligence Tools for Enterprise Document Processing.

Provides deterministic regex and rule engines for:
- Redaction & PII anonymization (Saudi National ID, Iqama, GCC IBAN, VAT/TIN, CR, phone, email)
- Fast document categorization & language detection (EN / AR)
- Financial statement metric extraction & ratio calculation
- Arithmetic, VAT 15%, and date anomaly auditing
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class BilingualDocumentKit:
    """Enterprise bilingual processing toolkit for Arabic and English documents."""

    # -----------------------------------------------------------------------
    # 1. Bilingual Redaction & PII Anonymization
    # -----------------------------------------------------------------------

    @staticmethod
    def redact_pii(text: str) -> Dict[str, Any]:
        """
        Redact sensitive PII in English and Arabic text.
        Masks National IDs, Iqama, IBANs, Credit Cards, Tax Numbers, Phones, and Emails.
        """
        findings: List[Dict[str, Any]] = []
        redacted = text

        patterns = [
            # Saudi / Gulf IBANs (e.g. SA0380000000608010167519, AE070331234567890123456, EG...)
            (
                r"\b(SA\d{2}[0-9A-Z]{20}|AE\d{21}|EG\d{27}|[A-Z]{2}\d{2}[0-9A-Z]{12,30})\b",
                "[REDACTED_IBAN / آيبان_محجوب]",
                "IBAN / الحساب البنكي الدولي",
            ),
            # Saudi Tax ID (ZATCA 15 digits starting and ending with 3: 3xxxxxxxxxxxx3)
            (
                r"\b(3\d{13}3)\b",
                "[REDACTED_TAX_ID / رقم_ضريبي_محجوب]",
                "Tax Identification Number / الرقم الضريبي",
            ),
            # Saudi National ID / Iqama (10 digits starting with 1 or 2)
            (
                r"\b([12]\d{9})\b",
                "[REDACTED_NATIONAL_ID / هوية_وطنية_أو_إقامة_محجوبة]",
                "National ID or Iqama / هوية وطنية أو إقامة",
            ),
            # US SSN (xxx-xx-xxxx)
            (
                r"\b(\d{3}-\d{2}-\d{4})\b",
                "[REDACTED_SSN / رقم_تأمين_محجوب]",
                "Social Security Number (SSN)",
            ),
            # Credit Card Numbers (13 to 19 digits with optional dashes/spaces)
            (
                r"\b(?:\d{4}[ -]?){3}\d{4}\b",
                "[REDACTED_CREDIT_CARD / بطاقة_ائتمان_محجوبة]",
                "Credit Card / بطاقة بنكية",
            ),
            # Email addresses
            (
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
                "[REDACTED_EMAIL / بريد_محجوب]",
                "Email Address / البريد الإلكتروني",
            ),
            # Saudi / Gulf Phone numbers (+966, 05x, +971, +20, etc.)
            (
                r"(?:\+966|00966|966)?0?5\d{8}\b|\+971\d{8,9}\b|\+20\d{10}\b|\+?1?\d{3}[-.\s]\d{3}[-.\s]\d{4}\b",
                "[REDACTED_PHONE / هاتف_محجوب]",
                "Phone Number / رقم الهاتف",
            ),
            # Commercial Registration (CR / سجل تجاري: 10 digits starting with 10, 20, 40, etc.)
            (
                r"(?:سجل\s*تجاري|CR|C\.R\.|س\.ت)[:\s#]*(\d{10})\b",
                "سجل تجاري: [REDACTED_CR / سجل_محجوب]",
                "Commercial Registration / السجل التجاري",
            ),
        ]

        for regex, mask, label in patterns:
            for match in re.finditer(regex, redacted, flags=re.IGNORECASE):
                val = match.group(0)
                findings.append({
                    "type": label,
                    "masked": mask,
                    "original_snippet": val[:3] + "•••" + val[-2:] if len(val) > 5 else "•••",
                })
            redacted = re.sub(regex, mask, redacted, flags=re.IGNORECASE)

        return {
            "redacted_text": redacted,
            "total_redactions": len(findings),
            "findings": findings,
            "status": "sanitized",
        }

    # -----------------------------------------------------------------------
    # 2. Bilingual Document Classification & Routing
    # -----------------------------------------------------------------------

    @staticmethod
    def classify_document(text: str) -> Dict[str, Any]:
        """
        Classify document category, language, and routing department in English and Arabic.
        """
        # 1. Detect language distribution
        arabic_chars = len(re.findall(r"[\u0600-\u06FF]", text))
        latin_chars = len(re.findall(r"[A-Za-z]", text))
        total_letters = arabic_chars + latin_chars or 1

        if arabic_chars / total_letters > 0.6:
            primary_lang = "ar"
            lang_label = "Arabic / العربية"
        elif latin_chars / total_letters > 0.6:
            primary_lang = "en"
            lang_label = "English / الإنجليزية"
        else:
            primary_lang = "mixed"
            lang_label = "Bilingual / مزدوج اللغة (AR & EN)"

        lower = text.lower()

        # Category profiles
        categories = {
            "INVOICE": {
                "name_en": "Tax Invoice / Billing",
                "name_ar": "فاتورة ضريبية / مطالبة مالية",
                "department": "Finance & Accounts Payable / المالية والمحاسبة",
                "keywords": [
                    "invoice", "tax invoice", "bill to", "subtotal", "vat", "due date", "فاتورة", "فاتورة ضريبية",
                    "الرقم الضريبي", "المجموع", "ضريبة القيمة المضافة", "تاريخ الاستحقاق", "المورد", "العميل"
                ],
            },
            "CONTRACT": {
                "name_en": "Legal Contract / Agreement",
                "name_ar": "عقد قانوني / اتفاقية ملزمة",
                "department": "Legal & Compliance / الشؤون القانونية",
                "keywords": [
                    "agreement", "contract", "parties", "indemnification", "jurisdiction", "termination", "hereby",
                    "عقد", "اتفاقية", "الطرف الأول", "الطرف الثاني", "البند", "المادة", "التعويض", "القانون الحاكم",
                    "فسخ العقد", "الاختصاص القضائي"
                ],
            },
            "FINANCIAL_STATEMENT": {
                "name_en": "Financial Statement / P&L",
                "name_ar": "قوائم مالية / ميزانية وأرباح وخسائر",
                "department": "Corporate Finance & Audit / المالية وإدارة التدقيق",
                "keywords": [
                    "balance sheet", "income statement", "cash flow", "ebitda", "net income", "gross profit", "assets",
                    "الميزانية العمومية", "قائمة الدخل", "التدفقات النقدية", "الأصول", "الخصوم", "صافي الربح", "إجمالي الإيرادات"
                ],
            },
            "RESUME": {
                "name_en": "Resume / CV",
                "name_ar": "سيرة ذاتية / ملف ترشيح",
                "department": "Human Resources & Talent Acquisition / الموارد البشرية",
                "keywords": [
                    "resume", "curriculum vitae", "education", "work experience", "skills", "bachelor", "master",
                    "سيرة ذاتية", "الخبرات المهنية", "المؤهلات العلمية", "المهارات", "التعليم", "جامعة", "بكالوريوس"
                ],
            },
            "COMMERCIAL_REGISTRATION": {
                "name_en": "Commercial Registration (CR)",
                "name_ar": "شهادة سجل تجاري أو ترخيص",
                "department": "Corporate Affairs & Governance / شؤون الشركات والترخيص",
                "keywords": [
                    "commercial registration", "ministry of commerce", "cr number", "license", "سجل تجاري",
                    "وزارة التجارة", "رقم السجل", "الاسم التجاري", "الكيان القانوني", "رأس المال"
                ],
            },
            "OFFICIAL_LETTER": {
                "name_en": "Official Letter / Government Circular",
                "name_ar": "خطاب رسمي / تعميم إداري",
                "department": "Executive Management / الإدارة التنفيذية",
                "keywords": [
                    "circular", "memorandum", "subject:", "dear sir", "respectfully", "تعميم", "خطاب", "سعادة",
                    "المحترمين", "السلام عليكم", "الموضوع", "إشارة إلى", "وتقبلوا خالص التحية"
                ],
            },
        }

        best_category = "GENERAL_DOCUMENT"
        best_score = 0
        best_info = {
            "name_en": "General Document",
            "name_ar": "مستند عام",
            "department": "Operations / العمليات",
        }

        for cat_id, info in categories.items():
            matches = sum(1 for kw in info["keywords"] if kw in lower)
            if matches > best_score:
                best_score = matches
                best_category = cat_id
                best_info = info

        confidence = min(0.99, max(0.40, best_score / 6.0))

        return {
            "category": best_category,
            "category_name_en": best_info["name_en"],
            "category_name_ar": best_info["name_ar"],
            "primary_language": primary_lang,
            "language_label": lang_label,
            "confidence": round(confidence, 2),
            "routing_department": best_info["department"],
            "priority": "URGENT / عاجل" if any(w in lower for w in ["urgent", "عاجل", "immediate", "فوري"]) else "NORMAL / عادي",
        }

    # -----------------------------------------------------------------------
    # 3. Bilingual Financial Statement Analysis
    # -----------------------------------------------------------------------

    @staticmethod
    def analyze_financial_statement(text: str) -> Dict[str, Any]:
        """
        Extract financial statements metrics, P&L numbers, and compute standard ratios.
        """
        metrics: Dict[str, Optional[float]] = {
            "revenue": None,
            "cogs": None,
            "gross_profit": None,
            "operating_expenses": None,
            "operating_income_ebit": None,
            "net_income": None,
            "total_assets": None,
            "total_liabilities": None,
            "equity": None,
        }

        # Regex patterns for financial line items (EN & AR)
        patterns = {
            "revenue": [
                r"(?:total\s+revenue|revenue|sales|الإيرادات|إجمالي\s+الإيرادات|المبيعات)[\s:]*[\$€£SAREGP]*\s*([\d,]+(?:\.\d+)?)",
            ],
            "gross_profit": [
                r"(?:gross\s+profit|إجمالي\s+الربح|مجمل\s+الربح)[\s:]*[\$€£SAREGP]*\s*([\d,]+(?:\.\d+)?)",
            ],
            "operating_income_ebit": [
                r"(?:operating\s+income|ebit|الربح\s+التشغيلي|الدخل\s+التشغيلي)[\s:]*[\$€£SAREGP]*\s*([\d,]+(?:\.\d+)?)",
            ],
            "net_income": [
                r"(?:net\s+income|net\s+profit|صافي\s+الربح|صافي\s+الدخل)[\s:]*[\$€£SAREGP]*\s*([\d,]+(?:\.\d+)?)",
            ],
            "total_assets": [
                r"(?:total\s+assets|إجمالي\s+الأصول|مجموع\s+الموجودات)[\s:]*[\$€£SAREGP]*\s*([\d,]+(?:\.\d+)?)",
            ],
            "total_liabilities": [
                r"(?:total\s+liabilities|إجمالي\s+الخصوم|مجموع\s+المطلوبات)[\s:]*[\$€£SAREGP]*\s*([\d,]+(?:\.\d+)?)",
            ],
            "equity": [
                r"(?:total\s+equity|shareholders['\s]+equity|إجمالي\s+حقوق\s+الملكية|حقوق\s+المساهمين)[\s:]*[\$€£SAREGP]*\s*([\d,]+(?:\.\d+)?)",
            ],
        }

        for key, p_list in patterns.items():
            for pat in p_list:
                m = re.search(pat, text, flags=re.IGNORECASE)
                if m:
                    try:
                        val_str = m.group(1).replace(",", "")
                        metrics[key] = float(val_str)
                        break
                    except ValueError:
                        pass

        # Compute standard ratios if metrics exist
        ratios: Dict[str, Any] = {}
        rev = metrics.get("revenue")
        gp = metrics.get("gross_profit")
        ni = metrics.get("net_income")
        assets = metrics.get("total_assets")
        liab = metrics.get("total_liabilities")
        eq = metrics.get("equity")

        if rev and gp and rev > 0:
            ratios["gross_margin_pct"] = round((gp / rev) * 100, 2)
        if rev and ni and rev > 0:
            ratios["net_profit_margin_pct"] = round((ni / rev) * 100, 2)
        if assets and liab and liab > 0:
            ratios["debt_to_assets_ratio"] = round(liab / assets, 2)
        if liab and eq and eq > 0:
            ratios["debt_to_equity_ratio"] = round(liab / eq, 2)

        # Detect currency
        currency = "USD"
        if any(c in text for c in ["SAR", "ريال", "ر.س", "سعودي"]):
            currency = "SAR (Saudi Riyal / ريال سعودي)"
        elif any(c in text for c in ["AED", "درهم", "د.إ"]):
            currency = "AED (UAE Dirham / درهم إماراتي)"
        elif any(c in text for c in ["EGP", "جنيه", "ج.م"]):
            currency = "EGP (Egyptian Pound / جنيه مصري)"
        elif any(c in text for c in ["€", "EUR", "يورو"]):
            currency = "EUR (Euro / يورو)"
        elif "$" in text or "USD" in text:
            currency = "USD (US Dollar / دولار أمريكي)"

        return {
            "currency": currency,
            "metrics": metrics,
            "financial_ratios": ratios,
            "summary_en": f"Extracted metrics for {currency} reporting.",
            "summary_ar": f"تم استخراج المؤشرات المالية المكتشفة بعملة {currency}.",
        }

    # -----------------------------------------------------------------------
    # 4. Anomaly, Fraud & VAT 15% Verification
    # -----------------------------------------------------------------------

    @staticmethod
    def audit_anomalies(text: str) -> Dict[str, Any]:
        """
        Audit arithmetic consistency, VAT 15% ZATCA calculation, and chronological dates.
        """
        anomalies: List[Dict[str, Any]] = []

        # 1. ZATCA / GCC VAT 15% Check
        subtotal_match = re.search(r"(?:subtotal|المجموع\s*قبل\s*الضريبة|المبلغ\s*الخاضع\s*للضريبة)[\s:]*[\$€£SAREGP]*\s*([\d,]+(?:\.\d+)?)", text, re.I)
        vat_match = re.search(r"(?:vat\s*(?:15%|15\s*%)?|ضريبة\s*القيمة\s*المضافة(?:\s*15%)?)[\s:]*[\$€£SAREGP]*\s*([\d,]+(?:\.\d+)?)", text, re.I)
        total_match = re.search(r"(?:total|الإجمالي|المجموع\s*الكلي)[\s:]*[\$€£SAREGP]*\s*([\d,]+(?:\.\d+)?)", text, re.I)

        if subtotal_match and vat_match and total_match:
            try:
                sub = float(subtotal_match.group(1).replace(",", ""))
                vat = float(vat_match.group(1).replace(",", ""))
                tot = float(total_match.group(1).replace(",", ""))

                # Check subtotal + vat == total
                expected_tot = round(sub + vat, 2)
                if abs(expected_tot - tot) > 0.05:
                    anomalies.append({
                        "category": "ARITHMETIC_ERROR / خطأ حسابي",
                        "severity": "HIGH / مرتفع",
                        "description_en": f"Subtotal ({sub}) + VAT ({vat}) = {expected_tot}, but Total stated is {tot}.",
                        "description_ar": f"المجموع الفرعي ({sub}) + الضريبة ({vat}) = {expected_tot}، بينما الإجمالي المسجل هو {tot}.",
                    })

                # Check 15% calculation if applicable
                expected_vat = round(sub * 0.15, 2)
                if abs(expected_vat - vat) > 0.10:
                    anomalies.append({
                        "category": "TAX_CALCULATION / خطأ احتساب الضريبة",
                        "severity": "MEDIUM / متوسط",
                        "description_en": f"Expected 15% VAT on {sub} is {expected_vat}, but {vat} is listed.",
                        "description_ar": f"قيمة ضريبة 15% المتوقعة على {sub} هي {expected_vat}، ولكن المسجل هو {vat}.",
                    })
            except ValueError:
                pass

        # 2. Date Inversion (e.g., due date before issue date)
        # Search for YYYY-MM-DD or DD/MM/YYYY
        date_pattern = r"\b(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})\b"
        all_dates = re.findall(date_pattern, text)
        if len(all_dates) >= 2:
            issue_match = re.search(r"(?:date|issue\s+date|تاريخ\s+الإصدار|التاريخ)[\s:]*(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})", text, re.I)
            due_match = re.search(r"(?:due\s+date|تاريخ\s+الاستحقاق)[\s:]*(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})", text, re.I)
            if issue_match and due_match:
                issue_d = issue_match.group(1)
                due_d = due_match.group(1)
                if issue_d > due_d and len(issue_d) == 10 and len(due_d) == 10:
                    anomalies.append({
                        "category": "DATE_INVERSION / تناقض التواريخ",
                        "severity": "CRITICAL / حرج",
                        "description_en": f"Due date ({due_d}) precedes Issue date ({issue_d}).",
                        "description_ar": f"تاريخ الاستحقاق ({due_d}) يسبق تاريخ الإصدار ({issue_d}).",
                    })

        risk_rating = "CLEAN / سليم"
        if any(a["severity"].startswith("CRITICAL") for a in anomalies):
            risk_rating = "CRITICAL_RISK / مخاطر حرجة"
        elif any(a["severity"].startswith("HIGH") for a in anomalies):
            risk_rating = "HIGH_RISK / مخاطر عالية"
        elif anomalies:
            risk_rating = "MEDIUM_RISK / تنبيه متوسط"

        return {
            "risk_rating": risk_rating,
            "total_anomalies": len(anomalies),
            "anomalies": anomalies,
            "is_clean": len(anomalies) == 0,
        }

