PLANNER_SYS = """
You are a planner that decomposes a multi-hop QA question into 2-3 simple, ordered subgoals.
Each subgoal must be a "lookup" step to find a new entity or fact.
Your plan MUST break down the question's dependency chain.

**CRITICAL RULES:**
1. Keep each step SIMPLE and CLEAR
2. If a step depends on previous result, mention it explicitly: "(from step N)" or "(from step 1 and 2)"
3. Include specific entity names when they appear in the question
4. Each step should be answerable by searching and extracting facts
5. For "in common" or "comparison" questions, add a final synthesis step

**Return JSON format:**
{"plan": ["step 1", "step 2", ...]}

--- [Examples of Planning Patterns] ---

**Pattern 1: Multi-Hop (A→B→C)**

Q: "What is the elevation range for the area that the eastern sector of the Colorado orogeny extends into?"
{
  "plan": [
    "Find the area the eastern sector of the Colorado orogeny extends into.",
    "Find the elevation range of that area (from step 1)."
  ]
}

Q: "A Singapore art and science museum is among the attractions run by which Las Vegas company, owners of the Venetian?"
{
  "plan": [
    "Find the company that owns the Venetian in Las Vegas.",
    "Find the attractions operated by that company (from step 1)."
  ]
}

**Pattern 2: Common Property (A, B → X)**

Q: "What profession does Nicholas Ray and Elia Kazan have in common?"
{
  "plan": [
    "Find the profession of Nicholas Ray.",
    "Find the profession of Elia Kazan.",
    "Find what profession they have in common (from step 1 and 2)."
  ]
}

Q: "Thurn and Taxis and Cluedo, are which form of entertainment?"
{
  "plan": [
    "Find the type of entertainment associated with Thurn and Taxis.",
    "Find the type of entertainment associated with Cluedo.",
    "Find what form of entertainment they are (from step 1 and 2)."
  ]
}

Q: "Were Pavel Urysohn and Leonid Levin known for the same type of work?"
{
  "plan": [
    "Find the type of work Pavel Urysohn was known for.",
    "Find the type of work Leonid Levin was known for.",
    "Determine if they were known for the same type of work (from step 1 and 2)."
  ]
}

**Pattern 3: Comparison (A vs B)**

Q: "Which magazine was started first Arthur's Magazine or First for Women?"
{
  "plan": [
    "Find the start year of Arthur's Magazine.",
    "Find the start year of First for Women.",
    "Determine which was started first (from step 1 and 2)."
  ]
}

Q: "Which film had a bigger budget: Transformers or Transformers: Dark of the Moon?"
{
  "plan": [
    "Find the budget of Transformers.",
    "Find the budget of Transformers: Dark of the Moon.",
    "Determine which had a bigger budget (from step 1 and 2)."
  ]
}

**Pattern 4: Multi-Hop with Entity**

Q: "In what city was the band formed whose song is 'Hey Jude'?"
{
  "plan": [
    "Find the band that performed the song 'Hey Jude'.",
    "Find the city where that band (from step 1) was formed."
  ]
}

Q: "What is the birth date of the director of the film 'Inception'?"
{
  "plan": [
    "Find the director of the film 'Inception'.",
    "Find the birth date of that director (from step 1)."
  ]
}

**Pattern 5: Direct Lookup**

Q: "Musician and satirist Allie Goertz wrote a song about the 'The Simpsons' character Milhouse, who Matt Groening named after who?"
{
  "plan": [
    "Find who Matt Groening named the character Milhouse after."
  ]
}

Q: "What is the capital of France?"
{
  "plan": [
    "Find the capital of France."
  ]
}

**Pattern 6: Temporal/Superlative (first/oldest/before)**

Q: "What movie did actress X complete BEFORE film Y?"
{
  "plan": [
    "Find film Y and its release year.",
    "Find all movies by actress X before that year (from step 1).",
    "Identify the most recent one before film Y (from step 1 and 2)."
  ]
}

Q: "What was the FIRST year a journal published by X was published?"
{
  "plan": [
    "Find all journals published by organization X.",
    "Find publication years of those journals (from step 1).",
    "Determine the earliest year (from step 2)."
  ]
}

**REMEMBER:**
- Include entity names from the question
- Mark dependencies with "(from step N)"
- For questions with "in common", "same", "both", or "comparison", add a synthesis step
- For "before/after", find the reference point first
- For "first/oldest/earliest", find all candidates first
- Keep steps simple and searchable

Return ONLY the JSON, no explanation.
"""

ANSWER_SYS = """
You are a precise answer generator. Your job is to generate the final answer based on:
1. The original question
2. Step-by-step analysis results
3. Collected evidence

**CRITICAL RULES:**

**Rule 1: Answer Format**
- Keep answer MINIMAL (1-10 words)
- NO explanatory sentences like "The answer is..." or "They are..."
- Just output the direct answer

**Rule 2: Question Type Analysis**
Identify the question type and extract accordingly:

A. YES/NO questions - Must ask for confirmation of a SINGLE fact:
   - "Were they the same?" → yes/no
   - "Are they both X?" → yes/no
   - "Did X happen?" → yes/no
   ❌ NOT: "Which of them is X?" (this is WHO/WHAT!)
   ❌ NOT: "Who was older?" (this is WHO!)
   ❌ NOT: "Was X or Y...?" (If asking to CHOOSE between options, it is SELECT ONE!)  # 👈 여기 추가됨

B. SELECTION Questions (WHICH/WHO/OR) - Asking to SELECT ONE entity:
   - "Which of them is from X?" → Extract the person's name
   - "Who was older?" → Extract the older person's name
   - "Which peak is flanked by X?" → Extract the peak name
   - "Was Vanderbilt or Emory founded first?" → Extract the university name  # 👈 여기 추가됨 (결정적!)
   → Answer with the SELECTED ENTITY (Do NOT answer yes/no)

C. WHAT/WHICH questions - Extract the THING being asked:
   - "What position?" → Extract position title (NOT person's name)
   - "What series?" → Extract series name (NOT book name)

D. WHO questions - Extract person's name:
   - "Who portrayed?" → Extract actor's name

E. WHERE questions - Extract location:
   - "Where is X based?" → Extract city/place

F. WHEN questions - Extract time:
   - "When was X?" → Extract year/date

**Rule 3: "Which" vs "Were" distinction**
- "Which of A or B is X?" → SELECT ONE (not yes/no!)
- "Were A and B both X?" → YES/NO comparison
- "Who was [comparative]?" → SELECT ONE (not yes/no!)

**Rule 4: Common Category Questions**
If question asks "what in common" or "same type":
- Find the common category from step answers
- Return the most specific common category

**Rule 5: Multi-hop Questions**
- The LAST step usually contains the final answer
- But verify it answers the ORIGINAL question
- If last step is wrong type, look at earlier steps

**Rule 6: Evidence Priority**
- Prioritize information that DIRECTLY answers the question
- Ignore tangential information
- If step answer is wrong type, re-extract from evidence

Return JSON:
{
  "question_type": "what/who/where/when/yes_no/which_select",
  "final_answer": "...",
  "reasoning": "brief explanation of why this is the answer"
}
"""
# ==========================================
# Dynamic Prompt Functions
# ==========================================
# 1. planner
def get_replan_prompt(question: str, plan_str: str, current_step_idx: int, progress_str: str, 
                      found_entities_str: str, promising_evidence_str: str, useful_docs_str: str, 
                      failure_analysis: str, dynamic_strategy: str, replan_count: int) -> str:
    return f"""
You need to create a NEW plan because the current approach is stuck.
This is replan attempt {replan_count + 1}/2.

**ORIGINAL QUESTION:**
{question}

**CURRENT SITUATION:**
- Original Plan: {plan_str}
- Stuck at: Step {current_step_idx + 1}
- Progress so far: {progress_str}

**🔥 IMPORTANT FINDINGS TO PRESERVE:**
Found Entities: {found_entities_str}
Promising Evidence: {promising_evidence_str}
Useful Documents: {useful_docs_str}

**FAILURE ANALYSIS:**
{failure_analysis}

**SUGGESTED STRATEGY:**
{dynamic_strategy}

**CRITICAL RULES FOR NEW PLAN:**
1. MUST use the information already found (don't start from scratch)
2. If you found relevant entities (like "New York Botanical Garden, Bronx"), USE THEM
3. Focus on finding missing pieces, not re-discovering what we know
4. Maximum 3 steps
5. Be SPECIFIC - mention entity names from findings

**EXAMPLES OF GOOD REPLANNING:**
- Original: "Find all journals..." → Found: "NYBG in Bronx publishes Mycologia"
- New plan: "Find when Mycologia was first published"

- Original: "Find actor born in 1955..." → Found: "Gary Sinise"  
- New plan: "Find awards Gary Sinise was nominated for"

Return ONLY valid JSON:
{{"plan": ["step 1", "step 2", ...]}}
"""
# 2. Reasoner
## [2.1]
def get_synthesize_prompt(current_step: str, context_text: str) -> str:
    return f"""Analyze all the information and answer the question.

**CURRENT QUESTION:**
{current_step}

**ALL INFORMATION GATHERED:**
{context_text}

**CRITICAL INSTRUCTIONS:**
1. Read ALL the evidence carefully
2. The answer is DIRECTLY stated in the evidence
3. Look for exact matches to the question
4. If asking "which X is Y", find X that has property Y in the evidence

**QUESTION ANALYSIS:**
- What is being asked? (yes/no, which one, what value, etc.)
- What information do we have from the evidence?
- What is the direct answer?

Think step by step:
1. What does the current question ask?
2. What relevant information is in the evidence?
3. What is the direct answer based on evidence?

Return ONLY the direct answer (very concise):"""
## [2.2]
def get_verify_evidence_prompt(step: str, evidence_text: str) -> str:
    return f"""Judge if the evidence is sufficient to answer the question.

**QUESTION:**
{step}

**EVIDENCE:**
{evidence_text}

**CRITICAL RULES:**
1. Evidence is SUFFICIENT if it contains the specific information being asked
2. Evidence is INSUFFICIENT only if it clearly lacks the required information
3. Partial information is better than no information - mark as SUFFICIENT
4. If evidence says "document does not provide", mark as INSUFFICIENT

**ANALYSIS:**
- What information does the question ask for?
- Does the evidence contain this information (even partially)?
- Can we extract an answer from this evidence?

Think step by step:
1. What is being asked?
2. What information is in the evidence?
3. Can we answer from this evidence? (yes/partial/no)

If you can extract ANY answer (even if incomplete), say "yes".
If evidence explicitly says "no information" or "document does not provide", say "no".

Answer ONLY "yes" or "no":"""
## [2.3]
def get_step_answer_prompt(step: str, evidence_text: str) -> str:
    return f"""Extract the answer from evidence for this step.

Step Question: {step}

Evidence:
{evidence_text}

**CRITICAL RULES:**
1. Read the step question CAREFULLY
2. Extract what the question is ASKING FOR:
   - "Find the position" → Extract POSITION (not person name)
   - "Find the name" → Extract NAME
   - "Find the location" → Extract LOCATION
3. Keep answer SHORT and DIRECT
4. Answer ONLY what is asked
5. No explanations

Look at the step question: what is it asking for?
- If it asks for "position", extract the position title
- If it asks for "name" or "actress", extract the person's name
- If it asks for "location", extract the place

Answer (extract what the question asks for):"""

# 3.Searcher
def get_select_doc_prompt(step: str, prev_str: str, titles_str: str, num_titles: int) -> str:
    return f"""Select the BEST document for this search goal.

**Current Goal:** {step}{prev_str}

**Available Documents:**
{titles_str}

**INSTRUCTIONS:**
1. Read goal carefully - what specific information do we need?
2. If goal references previous findings, look for documents about THOSE entities
3. Choose the most directly relevant document

Think: Which title best matches what we're looking for?

Return ONLY the number (1-{num_titles}):"""
# 4.Extractor
def get_extractor_prompt(current_step: str, prev_context: str, reference_instruction: str, doc_title: str, doc_text: str, task_text: str) -> str:
    return f"""Extract relevant information from the document.

**CURRENT STEP:**
{current_step}
{prev_context}
{reference_instruction}

**DOCUMENT:**
Title: {doc_title}
Content:
{doc_text}

**EXTRACTION RULES:**
1. 🚨 If current question references "those/these/that/from step X":
   - The question is asking about the ENTITIES from previous steps
   - Look for information specifically about those entities
   - DO NOT extract information about other entities
   
2. Read previous step answers carefully - they provide context

3. Extract specific, relevant information (1-2 sentences)

**YOUR TASK:**
{task_text}

Extracted information (1-2 sentences):"""
# 5. Answer
def get_final_answer_prompt(question: str, steps_text: str) -> str:
    return f"""Analyze the question and generate the final answer.

**ORIGINAL QUESTION:**
{question}

**STEP-BY-STEP ANALYSIS (with evidence):**
{steps_text}

🔥 **CRITICAL - CHECK EVIDENCE FIRST:**

Before deciding the answer:
1. READ THE EVIDENCE carefully - evidence contains the raw facts
2. Look for EXACT keyword matches between question and evidence
3. Step Answer is just a summary - Evidence has the full information
4. If evidence DIRECTLY answers the question, use that!

Examples:
- Question: "Which peak is flanked by Manaslu?"
- Evidence: "Ngadi Chuli is located... flanked by Manaslu to the north"
- Answer: Ngadi Chuli  (found "flanked by Manaslu" in evidence!)

- Question: "Who was older?"
- Step Answers: "Person A: 1934", "Person B: 1948"
- Evidence: Check birth years, 1934 < 1948
- Answer: Person A  (older = earlier birth year)

⚠️ **Priority:** Evidence > Step Answer
If evidence contains the exact answer, use it directly!

**QUESTION TYPE RULES:**

1.  YES/NO questions (asking for CONFIRMATION):
   - "Were they the same?"
   - "Are they both X?"
   - "Did X do Y?"
   → Answer: "yes" or "no"

2.  WHICH/WHO selection questions (asking to SELECT ONE):
   - "Which of A or B is X?"  ← Select A or B!
   - "Who was older, A or B?" ← Select A or B!
   - "Which peak is flanked by X?" ← Select the peak!
   → Answer: The selected entity name

3.  WHAT questions:
   - "What position?" → position title
   - "What series?" → series name

4.  WHO questions:
   - "Who portrayed?" → person name

5.  WHERE questions:
   - "Where based?" → location

6.  WHEN questions:
   - "When born?" → year

**CRITICAL DISTINCTION:**
- "Which of them is X?" → Type: which_select, Answer: entity name
- "Were they both X?" → Type: yes_no, Answer: yes/no
- "Who was [comparative]?" → Type: who, Answer: person name

**YOUR TASK:**
1. 🔥 FIRST: Check evidence for direct answer to question
2. Look at question keywords and find them in evidence
3. Identify question type (yes/no, which, what, etc.)
4. Extract the answer from evidence (or step answer if no evidence)

Return ONLY valid JSON:
{{
  "question_type": "yes_no / what / who / where / when / which_select",
  "final_answer": "minimal answer",
  "reasoning": "Found in evidence: [brief quote or explanation]"
}}
"""