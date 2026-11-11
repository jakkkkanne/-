// The 12 animals of the Japanese Eto (干支).
// In Japan the animal year changes on January 1 (not Lunar New Year).
const ETO = [
  { k: '子', kana: 'ね', romaji: 'Ne', en: 'Rat', ord: 'first', traits: ['Clever', 'Resourceful', 'Quick-witted'] },
  { k: '丑', kana: 'うし', romaji: 'Ushi', en: 'Ox', ord: 'second', traits: ['Diligent', 'Steady', 'Honest'] },
  { k: '寅', kana: 'とら', romaji: 'Tora', en: 'Tiger', ord: 'third', traits: ['Brave', 'Confident', 'Bold'] },
  { k: '卯', kana: 'う', romaji: 'U', en: 'Rabbit', ord: 'fourth', traits: ['Gentle', 'Elegant', 'Kind'] },
  { k: '辰', kana: 'たつ', romaji: 'Tatsu', en: 'Dragon', ord: 'fifth', traits: ['Powerful', 'Ambitious', 'Lucky'] },
  { k: '巳', kana: 'み', romaji: 'Mi', en: 'Snake', ord: 'sixth', traits: ['Wise', 'Intuitive', 'Calm'] },
  { k: '午', kana: 'うま', romaji: 'Uma', en: 'Horse', ord: 'seventh', traits: ['Energetic', 'Free-spirited', 'Warm'] },
  { k: '未', kana: 'ひつじ', romaji: 'Hitsuji', en: 'Sheep', alt: 'Goat', ord: 'eighth', traits: ['Gentle', 'Creative', 'Peaceful'] },
  { k: '申', kana: 'さる', romaji: 'Saru', en: 'Monkey', ord: 'ninth', traits: ['Playful', 'Smart', 'Curious'] },
  { k: '酉', kana: 'とり', romaji: 'Tori', en: 'Rooster', ord: 'tenth', traits: ['Honest', 'Hardworking', 'Confident'] },
  { k: '戌', kana: 'いぬ', romaji: 'Inu', en: 'Dog', ord: 'eleventh', traits: ['Loyal', 'Faithful', 'Kind'] },
  { k: '亥', kana: 'い', romaji: 'I', en: 'Boar', ord: 'twelfth', traits: ['Generous', 'Sincere', 'Joyful'] },
];
ETO.forEach((e, i) => { e.idx = i; e.jpYear = '干支 第' + '一二三四五六七八九十'.split('').concat(['十一', '十二'])[i] + '番'; });

// Animal for a Gregorian year (Japanese rule: changes on Jan 1). 2020 = Rat.
function etoOfYear(y) { return ETO[((y - 2020) % 12 + 12) % 12]; }
// Recent birth years for an animal, e.g. Sheep → 1955 … 2027
function yearsOf(e) { const out = []; for (let y = 1948; y <= 2031; y++) if (etoOfYear(y) === e) out.push(y); return out.slice(-6); }
