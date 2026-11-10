/* Local PCM capture only. This worklet has no network access or provider keys. */
class AzulMicProcessor extends AudioWorkletProcessor {
  constructor() { super(); this.samples = new Float32Array(2048); this.offset = 0; }
  process(inputs) {
    const channel = inputs[0]?.[0];
    if (channel) for (const sample of channel) {
      this.samples[this.offset++] = sample;
      if (this.offset === this.samples.length) {
        let power = 0;
        for (const value of this.samples) power += value * value;
        this.port.postMessage({samples:this.samples, rms:Math.sqrt(power / this.samples.length)}, [this.samples.buffer]);
        this.samples = new Float32Array(2048); this.offset = 0;
      }
    }
    return true;
  }
}
registerProcessor('azul-mic', AzulMicProcessor);
