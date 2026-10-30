import {
  FileText,
  ListChecks,
  Table2,
  ClipboardCheck,
  CreditCard,
  Receipt,
  UserCheck,
  ShieldAlert,
  FileSignature,
  ScanText,
  SearchCheck,
  ShieldBan,
  Tags,
  TrendingUp,
  Languages,
  Calculator,
} from "lucide-react";

export type LocalizedText = { en: string; ar: string };
const text = (en: string, ar: string): LocalizedText => ({ en, ar });

export const serviceCategories = [
  { id: "all", label: text("All services", "كل الخدمات") },
  { id: "finance", label: text("Invoices & finance", "الفواتير والمالية") },
  { id: "legal", label: text("Contracts & privacy", "العقود والخصوصية") },
  { id: "hr", label: text("Resumes", "السير الذاتية") },
  { id: "extraction", label: text("Forms & data", "النماذج والبيانات") },
  { id: "general", label: text("Reading & translation", "القراءة والترجمة") },
] as const;

// IDs match the existing playground and API service selectors.
export const serviceCatalog = [
  {
    id: "chat",
    category: "general",
    icon: FileText,
    credits: 1,
    title: text("Document chat", "محادثة مع المستند"),
    description: text(
      "Ask questions about a file and review the source references in the answer.",
      "اطرح أسئلة عن الملف وراجع المراجع المصدرية في الإجابة.",
    ),
    output: text(
      "Answers with document references",
      "إجابات مع مراجع من المستند",
    ),
  },
  {
    id: "summary",
    category: "general",
    icon: ListChecks,
    credits: 10,
    title: text("Document summary", "تلخيص المستند"),
    description: text(
      "Read a shorter version of a report, including its main points and important figures.",
      "احصل على نسخة مختصرة من التقرير تتضمن أهم النقاط والأرقام.",
    ),
    output: text("A summary with key findings", "ملخص بأهم النتائج"),
  },
  {
    id: "extraction",
    category: "extraction",
    icon: Table2,
    credits: 15,
    title: text("Data extraction", "استخراج البيانات"),
    description: text(
      "Collect names, dates, figures and tables from a document for review or reuse.",
      "اجمع الأسماء والتواريخ والأرقام والجداول من المستند لمراجعتها أو إعادة استخدامها.",
    ),
    output: text(
      "Structured tables with source references",
      "جداول منظمة مع مراجع المصدر",
    ),
  },
  {
    id: "form_parser",
    category: "extraction",
    icon: ClipboardCheck,
    credits: 20,
    title: text("Form reading", "قراءة النماذج"),
    description: text(
      "Read field values, selected checkboxes and signature details from completed forms.",
      "استخرج قيم الحقول وخانات الاختيار المحددة وتفاصيل التوقيع من النماذج المعبأة.",
    ),
    output: text(
      "Field names, values and missing fields",
      "أسماء الحقول وقيمها والحقول الناقصة",
    ),
  },
  {
    id: "receipt",
    category: "finance",
    icon: CreditCard,
    credits: 20,
    title: text("Receipt processing", "معالجة الإيصالات"),
    description: text(
      "Extract the merchant, purchase date, items, tax and total from a receipt.",
      "استخرج اسم المتجر وتاريخ الشراء والأصناف والضريبة والإجمالي من الإيصال.",
    ),
    output: text("Itemized receipt data", "بيانات الإيصال حسب الصنف"),
  },
  {
    id: "invoice",
    category: "finance",
    icon: Receipt,
    credits: 25,
    title: text("Invoice processing", "معالجة الفواتير"),
    description: text(
      "Extract supplier details, line items, payment dates and totals. Check the arithmetic.",
      "استخرج بيانات المورد والبنود ومواعيد الدفع والمبالغ الإجمالية، وراجع العمليات الحسابية.",
    ),
    output: text(
      "Invoice fields and calculation checks",
      "حقول الفاتورة ومراجعة الحسابات",
    ),
  },
  {
    id: "resume",
    category: "hr",
    icon: UserCheck,
    credits: 25,
    title: text("Resume reading", "قراءة السير الذاتية"),
    description: text(
      "Organize a candidate’s contact details, skills, work history and education.",
      "نظّم بيانات الاتصال والمهارات والخبرات المهنية والتعليم الخاصة بالمرشح.",
    ),
    output: text("A structured candidate profile", "ملف مرشح منظم"),
  },
  {
    id: "compliance",
    category: "legal",
    icon: ShieldAlert,
    credits: 30,
    title: text("Sensitive data review", "مراجعة البيانات الحساسة"),
    description: text(
      "Find personal information and exposed credentials that may need to be removed before sharing.",
      "اعثر على المعلومات الشخصية وبيانات الدخول المكشوفة التي قد تحتاج إلى إزالتها قبل المشاركة.",
    ),
    output: text(
      "Flagged details and masking suggestions",
      "بيانات محددة واقتراحات لإخفائها",
    ),
  },
  {
    id: "contract",
    category: "legal",
    icon: FileSignature,
    credits: 35,
    title: text("Contract review", "مراجعة العقود"),
    description: text(
      "Find the parties, dates, obligations and clauses that need closer review.",
      "حدد أطراف العقد والتواريخ والالتزامات والبنود التي تحتاج إلى مراجعة أدق.",
    ),
    output: text(
      "Key terms and clauses to review",
      "الشروط الأساسية والبنود للمراجعة",
    ),
  },
  {
    id: "google_ai",
    category: "general",
    icon: ScanText,
    credits: 40,
    title: text("Document layout analysis", "تحليل بنية المستند"),
    description: text(
      "Read document sections, form fields and tables using the Google AI workflow.",
      "اقرأ أقسام المستند وحقول النماذج والجداول باستخدام مسار عمل Google AI.",
    ),
    output: text(
      "Document structure and extracted content",
      "بنية المستند والمحتوى المستخرج",
    ),
  },
  {
    id: "research",
    category: "general",
    icon: SearchCheck,
    credits: 50,
    title: text("Document research", "البحث في المستند"),
    description: text(
      "Compare claims across sections and collect the supporting passages from your file.",
      "قارن الادعاءات بين الأقسام واجمع المقاطع الداعمة لها من ملفك.",
    ),
    output: text(
      "Findings, references and evidence gaps",
      "نتائج ومراجع وثغرات في الأدلة",
    ),
  },
  {
    id: "redaction",
    category: "legal",
    icon: ShieldBan,
    credits: 25,
    title: text("Sensitive data masking", "إخفاء البيانات الحساسة"),
    description: text(
      "Mask detected IDs, bank details, tax numbers and contact information in Arabic or English text.",
      "أخفِ أرقام الهوية والبيانات البنكية والأرقام الضريبية ومعلومات الاتصال المكتشفة في النص العربي أو الإنجليزي.",
    ),
    output: text(
      "Masked text and a list of detected details",
      "نص مخفي البيانات وقائمة بالتفاصيل المكتشفة",
    ),
  },
  {
    id: "classifier",
    category: "extraction",
    icon: Tags,
    credits: 15,
    title: text("Document classification", "تصنيف المستندات"),
    description: text(
      "Identify the document type, language and suggested department for handling it.",
      "حدد نوع المستند ولغته والقسم المقترح للتعامل معه.",
    ),
    output: text(
      "Document category and routing suggestions",
      "فئة المستند واقتراحات توجيهه",
    ),
  },
  {
    id: "financial_statement",
    category: "finance",
    icon: TrendingUp,
    credits: 35,
    title: text("Financial statement review", "مراجعة القوائم المالية"),
    description: text(
      "Extract revenue, expenses, assets and liabilities, then calculate financial ratios.",
      "استخرج الإيرادات والمصروفات والأصول والالتزامات، ثم احسب النسب المالية.",
    ),
    output: text(
      "Financial figures and calculated ratios",
      "أرقام مالية ونسب محسوبة",
    ),
  },
  {
    id: "translation",
    category: "general",
    icon: Languages,
    credits: 30,
    title: text(
      "Arabic–English translation",
      "الترجمة بين العربية والإنجليزية",
    ),
    description: text(
      "Translate document text between Arabic and English, including legal and financial terms.",
      "ترجم نص المستند بين العربية والإنجليزية، بما في ذلك المصطلحات القانونية والمالية.",
    ),
    output: text(
      "Translated text with terminology notes",
      "نص مترجم مع ملاحظات على المصطلحات",
    ),
  },
  {
    id: "anomaly_audit",
    category: "finance",
    icon: Calculator,
    credits: 30,
    title: text("Invoice calculation checks", "مراجعة حسابات الفواتير"),
    description: text(
      "Check subtotals, tax amounts and date order, and flag possible inconsistencies.",
      "راجع المجاميع الفرعية والمبالغ الضريبية وترتيب التواريخ، وحدد الاختلافات المحتملة.",
    ),
    output: text(
      "Calculation differences to review",
      "اختلافات حسابية تحتاج إلى مراجعة",
    ),
  },
] as const;
