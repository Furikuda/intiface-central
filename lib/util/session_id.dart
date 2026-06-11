import 'dart:math';

/// Generates a human-shareable, hard-to-guess session ID for Client Mode: a
/// hyphen-joined passphrase of [wordCount] words drawn (with a cryptographically
/// secure RNG) from [_words]. Easy to read aloud / type, while the combined
/// keyspace — backed by server-side rate limiting on the entry form — makes
/// online guessing impractical. e.g. "brave-otter-lunar-pebble".
String generateSessionId({int wordCount = 4}) {
  final rng = Random.secure();
  return List.generate(
    wordCount,
    (_) => _words[rng.nextInt(_words.length)],
  ).join("-");
}

// Short, unambiguous words (no look-alikes). ~150 entries -> ~28 bits over 4
// words; the form's rate limiting is what actually stops brute force.
const List<String> _words = [
  "amber", "anchor", "apple", "arrow", "atlas", "autumn", "bacon", "badge",
  "bamboo", "banjo", "basil", "beacon", "bison", "blossom", "bottle", "brave",
  "breeze", "bronze", "brook", "bubble", "cactus", "candle", "canyon", "carbon",
  "cedar", "cherry", "chili", "cinder", "cloud", "clover", "cobalt", "comet",
  "copper", "coral", "cosmos", "cotton", "crane", "crimson", "crystal", "dahlia",
  "daisy", "dawn", "delta", "denim", "diamond", "dolphin", "dragon", "dune",
  "eagle", "ember", "emerald", "falcon", "fern", "fizz", "flame", "flint",
  "forest", "fossil", "garnet", "ginger", "glacier", "granite", "harbor", "hazel",
  "helium", "hickory", "honey", "ivory", "jade", "jasmine", "jasper", "jungle",
  "juniper", "kelp", "kettle", "lagoon", "lantern", "ledger", "lemon", "lichen",
  "lilac", "linen", "lotus", "lunar", "magnet", "mango", "maple", "marble",
  "meadow", "meteor", "mint", "mocha", "monsoon", "moss", "nectar", "nickel",
  "nimbus", "noble", "nova", "oasis", "ocean", "olive", "onyx", "orbit",
  "otter", "oxide", "pebble", "pepper", "petal", "pewter", "pigeon", "pine",
  "planet", "pollen", "poppy", "prairie", "pumpkin", "quartz", "quill", "quiver",
  "radish", "raisin", "raven", "ribbon", "river", "rocket", "rose", "rumble",
  "saffron", "sage", "sandal", "sapphire", "satin", "shadow", "shale", "shrub",
  "silver", "sleet", "spark", "spruce", "stone", "summit", "sunset", "tangerine",
  "thicket", "thistle", "thunder", "timber", "topaz", "tulip", "tundra", "umber",
  "valley", "velvet", "violet", "walnut", "willow", "winter", "yarrow", "zephyr",
];
