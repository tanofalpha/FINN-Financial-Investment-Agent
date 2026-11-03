# FINN — AI-Assisted Engineering Build History

**Project:** FINN — Financial Investment Agent  
**Developer:** Harshit, IIT Kanpur  
**GitHub:** https://github.com/tanofalpha/FINN-Financial-Investment-Agent

## 1. Development Approach

I developed FINN using an iterative, AI-assisted engineering workflow. I used LLM-based assistants to accelerate architecture exploration, implementation, debugging, and refinement, while using local execution, terminal logs, and generated financial reports to evaluate their suggestions.

My objective was not simply to produce working code, but to build an investment research prototype that is cost-conscious, source-grounded, and useful to an investor.

A significant part of the development process involved identifying weaknesses in initially generated solutions and using real execution results to guide subsequent improvements.

## 2. Designing the Research Pipeline

For the Pull Engine, I worked with AI assistance to develop a multi-stage financial research workflow:

- Retrieve financial information and company disclosures from Screener.in.
- Extract text from annual reports and earnings-call transcripts.
- Identify explicit, forward-looking management guidance.
- Compare those statements against reported quarterly financial results.
- Generate business summaries and evidence-based bull/bear arguments.

The initial design separated document extraction from LLM reasoning, with PDF caching and prompt-based response caching to reduce repeated processing costs.

An important design consideration was restricting financial conclusions to supplied company disclosures rather than allowing the model to introduce unsupported external information.

## 3. Debugging and Iteration: Key Examples

### Iteration A — Gemini API reliability

During the first live execution for `TATAELXSI`, Gemini requests failed with a 120-second read timeout.

I used the traceback to investigate the failure with AI assistance. The original implementation retried selected HTTP status codes but did not properly handle network timeout exceptions.

The retry logic was subsequently revised to include timeout handling, connection errors, and exponential backoff.

A second run returned HTTP 503 on all four attempts. Rather than continuing to increase the timeout, I tested a different Gemini model configuration.

Switching from `gemini-flash-latest` to `gemini-3.5-flash-lite` allowed the initial research pipeline to complete, producing a JSON research output containing three extracted guidance items.

**Engineering lesson:** Reliable AI integrations need explicit failure handling, model configurability, and observability. A successful API integration must account for provider availability, not just successful responses.

### Iteration B — Evaluating financial output quality

Although the pipeline completed successfully, examining its research output revealed several problems:

- Quarterly data included historical periods from 2012–2015 instead of the recent quarters needed for analysis.
- The annual report was not being correctly discovered.
- Duplicate transcript URLs reduced the diversity of source material.
- The newest management guidance covered future periods, making some promised-versus-delivered comparisons premature.

These were data-quality and financial-reasoning issues rather than execution errors.

I used the output to guide another iteration with AI assistance, focusing on recent period selection, source deduplication, expanded annual-report discovery, and stricter period alignment.

The proposed improvements also required the model to distinguish between genuinely missed guidance and guidance whose reporting period had not yet ended.

**Engineering lesson:** Successful code execution does not establish analytical correctness. Source freshness, reporting periods, and evidence quality are essential for financial applications.

### Iteration C — Source discovery and Windows compatibility

After updating the research pipeline, I ran it again against live Screener.in data.

The revised extraction logic identified:

- 35 earnings-call transcript links.
- 15 annual-report links.

This confirmed that the revised link discovery was identifying substantially more source material. It did not, by itself, establish that every document had been downloaded or analyzed.

The subsequent execution exposed a new issue:

`UnicodeEncodeError: 'charmap' codec can't encode character '\ufb01'`

The error occurred when the script attempted to write extracted PDF text using Windows' default `cp1252` encoding.

I used the full traceback to diagnose the failure with AI assistance. The corrective approach was to use explicit UTF-8 encoding for cached PDF text and invalidate potentially incomplete cache files.

**Engineering lesson:** Real-world document pipelines must account for operating-system differences, Unicode characters, incomplete writes, and corrupted cache states.

## 4. How I Used AI Versus My Own Validation

AI assistants contributed candidate implementations, debugging explanations, refactoring suggestions, and alternative design approaches.

My workflow involved taking these suggestions into the local project, running the relevant commands, checking execution results, and returning observed failures or incorrect financial output for further refinement.

For example, AI-generated changes to transcript parsing were not treated as verified merely because they were syntactically valid. I checked them against actual company disclosures and reported the observed discovery counts and runtime failures.

This iterative process exposed problems that were not apparent in isolated code examples or simulated tests.

The interaction history therefore includes unsuccessful attempts, corrected assumptions, and subsequent iterations, rather than only the final code.

## 5. Engineering Trade-offs

**Cost versus analytical depth:** Separating lower-cost document extraction from stronger financial synthesis helps control inference costs. PDF and prompt caching further reduce repeated requests.

**Accuracy versus coverage:** I prioritized explicit management statements and identifiable reporting periods. Where there is insufficient evidence of delivery, the system should return an uncertain verdict rather than manufacture a conclusion.

**Reliability versus complexity:** A snapshot-based frontend provides predictable performance and an accessible demonstration experience, while the Python pipeline handles document ingestion and research generation separately.

**Speed versus validation:** AI accelerated implementation and debugging, but the initial output demonstrated why generated analysis still requires independent verification.

## 6. Current Limitations and Next Steps

The development history also exposed opportunities for improvement.

The next engineering steps are to validate the revised research pipeline end to end, strengthen period matching between management guidance and reported results, improve source citations, and add automated regression tests for financial table parsing.

I would also introduce structured extraction validation, atomic cache writes, and clearer separation of model selection between low-cost extraction and deeper synthesis.

## 7. Supporting AI Conversation History

The following original conversations document the development and debugging process:

- **Research pipeline design and implementation:** [Insert original conversation link]
- **Gemini timeout, HTTP 503, and model selection:** [Insert original conversation link]
- **Financial data quality and transcript extraction revisions:** [Insert original conversation link]
- **Unicode/PDF caching error diagnosis:** [Insert original conversation link]
- **Additional coding-agent conversations, where applicable:** [Insert links]

These conversations are provided as direct evidence of how I worked with AI tools, evaluated their output, and iterated on the application.

---

**Summary**

FINN reflects an AI-assisted development process combining rapid prototyping with practical debugging and validation. The most valuable iterations emerged not from the first generated solution, but from identifying where working code still produced incomplete or unreliable financial analysis and improving the system accordingly.
