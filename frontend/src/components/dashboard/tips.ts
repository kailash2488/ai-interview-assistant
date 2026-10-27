/** Short, practical interview advice shown on the dashboard and before an interview starts. */
export const TIPS: Array<{ title: string; text: string }> = [
  { title: 'Use the STAR shape', text: 'For behavioural questions give the Situation, the Task, what you did (Action) and the Result. Spend most of your time on the action and the result.' },
  { title: 'Say "I", not only "we"', text: 'Interviewers want to know what you did. Describe the team, then be specific about your own part and decisions.' },
  { title: 'Put numbers on it', text: 'Latency cut by 40%, 2 million requests a day, a report that went from 8 seconds to 90 ms. One real number makes an answer memorable.' },
  { title: 'Name the trade-off', text: 'For technical questions, say what you chose, what you gave up and why. Saying "it depends on X" and then explaining X shows depth.' },
  { title: 'Start with the point', text: 'Give your answer in one sentence first, then support it with an example. It keeps you from rambling and helps the interviewer follow.' },
  { title: 'Clarify before you answer', text: 'If a question is broad, ask what scale or constraints they have in mind. It is expected, and it buys you a moment to think.' },
  { title: "It's fine to say you don't know", text: "Say what you do know, and how you would find out. That is far better than guessing confidently and being wrong." },
  { title: 'Aim for one to two minutes', text: 'Most answers fit in 60 to 120 seconds. Shorter usually lacks an example; longer loses the listener.' },
  { title: 'Mirror the job description', text: 'Use the language of the posting for the skills you really have. Match your best examples to its must-haves.' },
  { title: 'Talk about a failure honestly', text: 'Pick a real mistake, own it, and spend most of the answer on what you changed afterwards.' },
  { title: 'Prepare your questions', text: 'Have two or three good questions about the team, the work and how success is measured. It shows genuine interest.' },
  { title: 'Think out loud', text: 'For design and debugging questions, narrate your reasoning. A good process matters more than a perfect answer.' },
]

/** The same tip all day, a different one tomorrow. */
export function tipOfTheDay(date = new Date()): number {
  const days = Math.floor(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / 86_400_000)
  return days % TIPS.length
}
