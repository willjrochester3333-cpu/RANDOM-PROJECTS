// What the coach says for each cue. Kept separate from the speech code so it
// can be unit tested and easily customised.

export function cueText(cue, verbosity = 'detailed') {
  const r = cue.rate;
  const zone = `${cue.zoneLow} to ${cue.zoneHigh}`;
  const short = verbosity === 'short';
  switch (cue.type) {
    case 'slow':
      if (short) return cue.strong ? 'Ease right off.' : 'Slow down.';
      return cue.strong
        ? `Ease right off. Breathing ${r}, well above ${cue.zoneHigh}.`
        : `${cue.repeat ? 'Still too fast. ' : ''}Slow down a little. Breathing ${r}, target ${zone}.`;
    case 'speed':
      if (short) return cue.strong ? 'Pick it up.' : 'Speed up.';
      return cue.strong
        ? `Pick it up. Breathing ${r}, well under ${cue.zoneLow}.`
        : `${cue.repeat ? 'Still easy. ' : ''}You can speed up. Breathing ${r}, target ${zone}.`;
    case 'inzone':
      return short ? 'In the zone.' : `Good, that's your zone. Breathing ${r}.`;
    case 'locked':
      return short ? `Breathing ${r}.` : `Got your breathing: ${r} a minute. Target ${zone}.`;
    case 'back':
      return short ? `Breathing ${r}.` : `I can hear you again. Breathing ${r}.`;
    case 'lost':
      return short ? 'No breathing signal.' : "I can't hear your breathing. Check the microphone.";
    case 'status': {
      const where = r === null ? '' : r > cue.zoneHigh ? ' Above target.' : r < cue.zoneLow ? ' Below target.' : ' In the zone.';
      return `${cue.minutes} minutes.${r === null ? '' : ` Breathing ${r}.`}${where}`;
    }
    case 'start':
      return short ? 'Coach on.' : `Breath coach on. Target ${zone} breaths a minute.`;
    case 'stop':
      return 'Run saved.';
    default:
      return '';
  }
}

/** Visual/semantic category of a cue, for tones, vibration and UI colour. */
export function cueKind(type) {
  if (type === 'slow') return 'down';
  if (type === 'speed') return 'up';
  if (type === 'inzone' || type === 'locked' || type === 'back') return 'good';
  if (type === 'lost') return 'warn';
  return 'info';
}
