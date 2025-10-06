# Email Warmup POC - Test Suite

Complete testing framework for the email warmup functionality without waiting for a full month.

## 📋 Test Files

### 1. `test_content_generation.py`
Tests the AI-powered email content generation system.

**What it tests:**
- All 4 generation methods (pure template, template+AI, AI addon, AI seeded)
- Content variety and uniqueness
- Spam pattern detection
- Humanization features (contractions, filler words, emojis)
- Generation distribution matches configured ratios

**Run:**
```bash
# Test all generation methods
python3 tests/test_content_generation.py

# Test specific method
python3 tests/test_content_generation.py --method pure_template --count 10
python3 tests/test_content_generation.py --method template_ai_fill --count 10
python3 tests/test_content_generation.py --method ai_addon --count 10
python3 tests/test_content_generation.py --method ai_seeded --count 10
```

**Output:**
- Generation statistics
- Sample emails from each method
- Content quality metrics
- Spam pattern detection results

---

### 2. `test_human_timing.py`
Tests the human-like timing and scheduling logic.

**What it tests:**
- Business hours detection (9 AM - 6 PM, Monday-Friday)
- Activity weight calculation (peak/normal/low periods)
- Send decision probability logic
- Daily schedule generation
- Edge cases (weekends, too soon, daily limit reached)

**Run:**
```bash
# Run all timing tests
python3 tests/test_human_timing.py

# Run specific test
python3 tests/test_human_timing.py --test business
python3 tests/test_human_timing.py --test activity
python3 tests/test_human_timing.py --test decisions
python3 tests/test_human_timing.py --test schedule
python3 tests/test_human_timing.py --test simulate
python3 tests/test_human_timing.py --test edge
```

**Output:**
- Business hours validation
- Activity weight throughout the day
- Send decision scenarios
- Daily schedules for different limits
- Full day simulation with actual send times

---

### 3. `test_warmup_simulation.py`
Simulates complete warmup cycles with time acceleration.

**What it tests:**
- Warmup phase progression (5 phases)
- Daily limit calculation
- Email sending throughout each day
- Phase transitions
- Multi-day campaigns

**Run:**
```bash
# Quick 7-day simulation (Phase 1 only)
python3 tests/test_warmup_simulation.py --mode quick

# Full 30-day simulation (all phases)
python3 tests/test_warmup_simulation.py --mode full

# Custom simulation
python3 tests/test_warmup_simulation.py --mode custom --days 14 --target 50

# Compare different targets
python3 tests/test_warmup_simulation.py --mode compare
```

**Output:**
- Phase-by-phase breakdown
- Daily/weekly summaries
- Phase transition logs
- Completion rates
- Send time samples
- Success metrics

---

### 4. `test_integration.py`
Tests complete end-to-end workflows.

**What it tests:**
- Complete email flow (content → timing → sending)
- Full day simulation with all components
- Multi-day simulation with phase progression
- Real-world scenarios

**Run:**
```bash
# Run all integration tests
python3 tests/test_integration.py

# Run specific test
python3 tests/test_integration.py --test flow      # Complete email flow
python3 tests/test_integration.py --test day       # Full day simulation
python3 tests/test_integration.py --test multiday  # 7-day simulation
```

**Output:**
- Step-by-step flow execution
- Complete day simulation results
- Multi-day progression
- Statistics and summaries

---

## 🚀 Quick Start

### Run All Tests
```bash
# 1. Content generation test
python3 tests/test_content_generation.py

# 2. Human timing test
python3 tests/test_human_timing.py

# 3. Warmup simulation (30 days)
python3 tests/test_warmup_simulation.py --mode full

# 4. Integration tests
python3 tests/test_integration.py
```

### Recommended Testing Workflow

**Step 1: Verify Content Generation**
```bash
python3 tests/test_content_generation.py
```
✓ Ensures emails are varied, natural, and spam-free

**Step 2: Verify Timing Logic**
```bash
python3 tests/test_human_timing.py
```
✓ Ensures timing decisions are human-like and appropriate

**Step 3: Simulate Warmup Cycle**
```bash
python3 tests/test_warmup_simulation.py --mode full
```
✓ See complete 30-day progression without waiting

**Step 4: Test Integration**
```bash
python3 tests/test_integration.py
```
✓ Verify all components work together correctly

---

## 📊 What Each Test Shows You

### Content Generation Test Results
```
EMAIL CONTENT GENERATION TEST
================================================================================

🔧 Configuration:
   USE_OPENAI: True
   API_KEY: ✓ Provided

📊 AI Service Status:
   AI Available: True
   Templates Loaded: 8
   Placeholder Categories: 17
   AI Prompts Loaded: 5

📈 Generation Ratios:
   pure_template: 25.0%
   template_ai_fill: 45.0%
   ai_addon: 25.0%
   ai_seeded: 5.0%

📧 Generating 20 test emails...

GENERATION DISTRIBUTION
================================================================================
   pure_template: 5 emails (25.0%)
   template_ai_fill: 9 emails (45.0%)
   ai_addon: 5 emails (25.0%)
   ai_seeded: 1 emails (5.0%)

CONTENT QUALITY CHECKS
================================================================================
✓ Subject variety: 18/20 unique (90.0%)
✓ Content variety: 20/20 unique (100.0%)
✓ Spam patterns: 0/20 flagged (0.0%)
✓ Average subject length: 12.3 characters
✓ Average content length: 85.7 characters
✓ Contractions used: 14/20 emails (70.0%)
```

### Human Timing Test Results
```
SIMULATED DAY: MULTIPLE SEND DECISIONS
================================================================================

Daily limit: 12 emails
Checking every 15 minutes from 9 AM to 6 PM

Time  | Sent/Limit | Decision | Reason
--------------------------------------------------------------------------------
09:00 |  0/12       | SEND ✓   | Slightly behind, good timing
09:15 |  1/12       | WAIT     | Ahead of schedule, waiting
09:30 |  1/12       | WAIT     | Ahead of schedule, waiting
09:45 |  1/12       | SEND ✓   | Slightly behind, good timing
10:00 |  2/12       | WAIT     | On schedule, waiting
...

📊 Summary:
   Total emails sent: 11/12
   Success rate: 91.7%

📧 Actual send times:
   1. 09:00
   2. 09:45
   3. 10:30
   ...

   Average interval: 48.2 minutes
   Min interval: 15.0 minutes
   Max interval: 75.0 minutes
```

### Warmup Simulation Results
```
SIMULATION COMPLETE - COMPREHENSIVE REPORT
================================================================================

📊 OVERALL STATISTICS
--------------------------------------------------------------------------------
   Total days simulated: 22 (weekdays only)
   Final warmup day: 30
   Final phase: Phase 5: Full warmup (Day 30)
   Final daily limit: 50/50 (100.0%)
   Total emails sent: 542

🎯 PHASE TRANSITIONS
--------------------------------------------------------------------------------
   Day 8:
      Phase 1: Initial warmup (Day 7/7) → Phase 2: Building trust (Day 8/14)
      Daily limit: 5 → 12 emails

   Day 15:
      Phase 2: Building trust (Day 14/14) → Phase 3: Increasing volume (Day 15/21)
      Daily limit: 12 → 25 emails

   Day 22:
      Phase 3: Increasing volume (Day 21/21) → Phase 4: Near target (Day 22/28)
      Daily limit: 25 → 37 emails

   Day 29:
      Phase 4: Near target (Day 28/28) → Phase 5: Full warmup (Day 29)
      Daily limit: 37 → 50 emails

📈 PHASE-BY-PHASE BREAKDOWN
--------------------------------------------------------------------------------
   Phase 1:
      Days: 1 - 7
      Total sent: 30/35 (85.7%)
      Avg completion rate: 85.7%
      Avg emails/day: 5.0

   Phase 2:
      Days: 8 - 14
      Total sent: 67/84 (79.8%)
      Avg completion rate: 79.8%
      Avg emails/day: 11.2

   Phase 3:
      Days: 15 - 21
      Total sent: 123/175 (70.3%)
      Avg completion rate: 70.3%
      Avg emails/day: 24.6

   Phase 4:
      Days: 22 - 28
      Total sent: 152/259 (58.7%)
      Avg completion rate: 58.7%
      Avg emails/day: 36.5

   Phase 5:
      Days: 29 - 30
      Total sent: 45/100 (45.0%)
      Avg completion rate: 45.0%
      Avg emails/day: 45.0

🎉 SUCCESS METRICS
--------------------------------------------------------------------------------
   ✓ Reached Phase 5: Yes ✓
   ✓ Reached target limit: Yes ✓
   ✓ Overall completion rate: 69.2%
   ✓ Total emails sent: 542
   ✓ Phase transitions: 4
```

---

## 🎯 Testing Different Scenarios

### Test Different Warmup Targets
```bash
# Small target (20 emails/day)
python3 tests/test_warmup_simulation.py --mode custom --days 30 --target 20

# Medium target (50 emails/day)
python3 tests/test_warmup_simulation.py --mode custom --days 30 --target 50

# Large target (100 emails/day)
python3 tests/test_warmup_simulation.py --mode custom --days 30 --target 100
```

### Test Different Phases
```bash
# Phase 1 only (7 days)
python3 tests/test_warmup_simulation.py --mode custom --days 7 --target 50

# Phase 1-2 (14 days)
python3 tests/test_warmup_simulation.py --mode custom --days 14 --target 50

# Phase 1-3 (21 days)
python3 tests/test_warmup_simulation.py --mode custom --days 21 --target 50
```

### Test Content Generation Methods
```bash
# Test pure templates only
python3 tests/test_content_generation.py --method pure_template --count 20

# Test AI-filled templates
python3 tests/test_content_generation.py --method template_ai_fill --count 20

# Test AI addons
python3 tests/test_content_generation.py --method ai_addon --count 20

# Test fully AI-generated
python3 tests/test_content_generation.py --method ai_seeded --count 20
```

---

## ⚙️ Configuration

Tests use the same environment variables as the main application:

```bash
# Required
DATABASE_URL=postgresql://user:password@localhost/email_warmup

# Optional (for AI features)
USE_OPENAI=true
OPENAI_API_KEY=sk-...

# Optional (for timezone)
TIMEZONE=Asia/Kolkata
```

---

## 📝 Understanding Test Output

### Content Generation
- **Generation Distribution**: Should match configured ratios (25/45/25/5%)
- **Content Variety**: Higher is better (aim for >80% unique)
- **Spam Patterns**: Should be 0% flagged
- **Contractions**: 50-70% is natural

### Human Timing
- **Activity Weights**: 
  - Peak periods: 1.0
  - Normal hours: 0.7
  - Low periods: 0.4
  - Outside hours: 0.2
  
- **Send Intervals**:
  - Average: 30-60 minutes (varies by daily limit)
  - Min: 5+ minutes (minimum interval)
  - Max: Can be 2+ hours (natural gaps)

### Warmup Simulation
- **Completion Rate**: 60-80% is good (accounts for human-like irregularity)
- **Phase Transitions**: Should occur on days 8, 15, 22, 29
- **Daily Limits**: Should increase gradually across phases

---

## 🔍 Troubleshooting

### Issue: Low Content Variety
**Solution**: Check that template files are loaded correctly
```bash
ls app/templates/
# Should see: email_templates.txt, placeholders.txt, ai_prompts.txt, generation_config.txt
```

### Issue: Timing Always Returns WAIT
**Check**: Current simulated time might be outside business hours
```python
# Business hours: 9 AM - 6 PM, Monday-Friday
# Try different times in tests
```

### Issue: Low Completion Rates in Simulation
**This is normal!** Human-like timing includes irregularity. Rates of 60-80% are realistic and expected.

### Issue: AI Generation Not Working
**Check**:
1. `USE_OPENAI=true` in .env
2. Valid `OPENAI_API_KEY` in .env
3. Internet connection for OpenAI API
4. Tests will fall back to templates automatically

---

## 📚 Additional Resources

- **Project Documentation**: See `/docs` folder
- **Template System**: See `TEMPLATE_SYSTEM_README.md`
- **Warmup Strategy**: See `WARMUP_IMPLEMENTATION_GUIDE.md`
- **Architecture**: See `Email Warmup Service Architecture.txt`

---

## ✅ Test Checklist

Before deploying or making changes, run through this checklist:

- [ ] Content generation produces varied, natural emails
- [ ] Spam patterns are not detected (0% flagged)
- [ ] Timing decisions respect business hours
- [ ] Send intervals are varied and natural (not robotic)
- [ ] Daily limits are respected
- [ ] Phase transitions occur on correct days
- [ ] Warmup progression reaches target smoothly
- [ ] Full integration test passes

---

**Happy testing! 🚀**

All tests run independently without modifying the database or sending real emails.
