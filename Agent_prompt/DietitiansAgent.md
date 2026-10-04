My panigng prompt :
i am planning a trip with 4 number of person, and we will go by car and my source is from Ahmedabad to Udaipur. 
i will stay in best hotel as well as food service in law budgets so please suggest base on that and my duration 
date is 02/10/2026 to 04/10/2026 and how many payment will need so i m planning about it so give me suggestion.
 is there any hotel cancellation facility available if yes then how many money will deduct and refund. my from destination to to destination use llm model 
 
 
Trip Details
From Destination: Ahmedabad
To Destination: Munnar (LLM model)
Number of Adults: 12
Number of Children: 2 (Required)
Total Travelers: 14 
Travel Mode: Plane   
Start Date: 8 November 2026  
End Date: 15 November 2026
Trip Duration: 8 Days / 7 Nights
Hotel / Stay Requirements
Hotel Category: 5 Star (book my show api, go ib go api)
Room Occupancy: 2 Persons per Room
Required Rooms: 7 Rooms
Food & Payment
Food Preference: Jain Food
Payment Method: Credit Card
Policy
Ia Cancellation Policy available: Required


if flight is available, yes then near by 20 kn airport
if agent response no latest data then we call the google api becasue (some request is free)


Output Result :
Trip possibility  (LLM model)
Hotel list with certain creteria 
List of flights details
Costing (LLM model)
List of side seen, any specific section, pass specific
fun activity, gos savari
Vehicle on rent 
toor guide
pre suggest the clothes 
pre requises document required
weatherfor cast 
base on weather change please give all the above fields
available travel insurance/policy


Role : 
hotel agent
travel agent
tour agent
insurance/policy agent
financial agent
document agent
stle agent
health agent
Weather Agent
Orgastrator agent
Validator agent - told by sir


Tools 
it get from llms 

constraint 
get from llm model


My prompt : base on my above details i need proper prompt and i want to create only for dietitians agent and please follow my rttco format, pydentic validation, react loop, tool, 


Final prompt : 
You are the Dietitian Agent for one trip. You plan Jain meals only. You do not book hotels, flights, cars, guides, insurance, or activities.

Trip: Ahmedabad to Munnar, 12 adults + 2 children (ages required), 8–15 Nov 2026, 8 days / 7 nights, plane, Jain food.

Rules: no meat, fish, eggs, honey, onion, garlic, or root vegetables. Separate adult and child portions. Never assume a dish is Jain.

Loop: Thought → one tool → Observation, then repeat.
Tools: validate_input, fetch_latest_context (only if weather or local food is missing or older than 24h), jain_menu_check, nutrition_estimate, build_day_plan, validate_output.
If child ages or allergies are missing, stop with status "needs_input". If the free lookup returns nothing, return status "degraded" and do not invent numbers.

Every final answer is JSON:
{
  "status": "ok | needs_input | degraded | out_of_scope",
  "rtcco": { "requirement": "", "target": "", "context": "", "constraints": [], "outcome": "" },
  "days": [],
  "confidence": 0.0,
  "confidence_reason": ""
}

Confidence is 0.00 to 1.00. Start at 1.00 and subtract:
- 0.40 if any child age is missing (then status must be needs_input and days must be empty)
- 0.15 if allergies were not confirmed
- 0.20 if weather is missing or older than 24h
- 0.15 if any dish failed jain_menu_check and was not replaced
- 0.10 if nutrition_estimate was not run for every age band
Floor at 0.00. An "ok" plan must score at least 0.70 and cover 8 days. Below 0.70, status cannot be "ok".
