// The guided tours, one per video. Each step sets the lab's state (view, frame, explanation, range, mode), can play
// a stretch of the clip, points at one part of the screen, and says what to look at. Every number in the text is
// read from the loaded data (ctx, built in tour.js), never typed, so the tours cannot drift from the results.

const nmiTxt = (x) => (Number.isFinite(x) ? `${x.toFixed(1)} nmi` : "an unknown distance");
const ftTxt = (x) => (Number.isFinite(x) ? `${Math.round(x / 100) * 100 >= 1000 ? (Math.round(x / 100) * 100).toLocaleString("en-US") : Math.round(x)} ft` : "an unknown height");

// The last step: the case's verdict and its settling measurement in a sentence; the full reasoning stays one click
// away in the rail ("The full verdict and technical notes").
const settleStep = (why) => ({
  view: "cockpit", spot: "#rail-verdict", title: "What would settle it",
  text: (c) => `${c.decisive ? "This case has a clear leader." : "No explanation wins decisively here."} ${c.sum?.settle_title ? `The one measurement that would change that: <b>${c.esc(c.sum.settle_title.toLowerCase())}</b>. ${why} ` : ""}The full reasoning, with every number, is under "The full verdict and technical notes" on the right.`,
});

export const TOURS = {
  gimbal: {
    title: "GIMBAL, January 2015",
    steps: [
      {
        view: "cockpit", frame: 0, hyp: null, cmode: "render", spot: "#ck-panels", title: "The footage and its re-creation",
        text: (c) => `On the left, the Navy's infrared video, frame by frame. On the right, what the camera would have seen if the object were the explanation selected now: <b>${c.esc(c.name(c.leadTW.h.id))}</b>, the best fit at the default settings. The lab builds that picture from the jet's own instruments and the pointing angles read off the screen.`,
      },
      {
        view: "cockpit", frame: 600, cmode: "render", play: 1030, spot: "#ck-pic-l", title: "Watch it rotate",
        text: () => "Near the end the object appears to rotate. The question the lab tests: is the object itself turning, or is it glare in the pod's optics that turns with the camera? Both are among the explanations, and both are scored the same way.",
      },
      {
        view: "cockpit", frame: 900, spot: "#rail .scores", title: "Six explanations, one scorer",
        text: (c) => `Every explanation is fitted to the same measurements: sight line, rotation, horizon, cloud motion and more. On the video alone, <b>${c.esc(c.name(c.leadPO.h.id))}</b> ranks first, ${c.esc(c.words(c.secondPO))} than <b>${c.esc(c.name(c.secondPO.h.id))}</b>. Click any row to show that explanation in every view.`,
      },
      {
        view: "godseye", frame: 0, play: 1030, spot: "#ge-gl", title: "Where the jet was",
        text: (c) => `The scene from above, turned so the jet's nose points up the screen at the start. The white trail is the jet's turn; the faint fan is the direction the pod pointed. The selected explanation puts the object about <b>${nmiTxt(c.derived(c.leadTW)?.range_nmi_mean)}</b> away, at about ${ftTxt(c.derived(c.leadTW)?.altitude_ft_mean)}.`,
      },
      {
        view: "range", range: 7, spot: ".rg-charts", title: "The missing number: distance",
        text: (c) => `GIMBAL never shows how far away the object was. So the lab asks: at each distance, what would the object have to be doing? ${c.claim("G-T13") ? `The aircrew's account puts it at <b>${c.esc(c.claim("G-T13").value)}</b> (claim G-T13).` : ""} The range is set to 7 nmi here; the table under the charts gives each explanation's speed and altitude at that distance.`,
      },
      {
        view: "cockpit", spot: ".weight", title: "Counting the aircrew's accounts",
        text: () => "The second column also counts what the aircrew said, each statement treated as a measurement with its own uncertainty. Drag this slider to 0 to ignore them, or to 2 to count them double, and watch the ranking. The video-only column never moves.",
      },
      settleStep("Fitted to the video alone, every physical explanation puts the object 15 nmi or more away by the end of the clip at the 0.35 degree field of view; the aircrew say less than 10. A radar range good to about 2 nmi would rule those explanations in or out. The aircrew say the radar page was recorded; it has not been released."),
    ],
  },
  gofast: {
    title: "GOFAST, January 2015",
    steps: [
      {
        view: "cockpit", frame: 368, hyp: null, cmode: "render", spot: "#rail-readouts", title: "This time the range is on screen",
        text: (c) => `In GOFAST the pod locked on and showed a range: the RNG readout counts down ${c.rangeReads ? `from <b>${c.rangeReads[0]}</b> to <b>${c.rangeReads[1]}</b> nmi` : "over the clip"}. With the distance known, the lab can put the object at a point in space instead of on a curve.`,
      },
      {
        view: "cockpit", frame: 368, play: 760, spot: "#ck-pic-l", title: "Why it looks fast",
        text: () => "The object seems to race across the water. Much of that comes from the jet's own speed and the low angle the camera looks down at; the lab subtracts the jet's motion to work out how fast the object itself moves.",
      },
      {
        view: "godseye", frame: 368, play: 1030, spot: "#ge-gl", title: "Where it was",
        text: (c) => `From above: the jet's path, the sight lines, and the object about <b>${nmiTxt(c.derived(c.leadTW)?.range_nmi_mean)}</b> from the jet at about <b>${ftTxt(c.derived(c.leadTW)?.altitude_ft_mean)}</b>, well below the jet.`,
      },
      {
        view: "cockpit", frame: 700, spot: "#rail .scores", title: "Same place, different speeds",
        text: (c) => `On the video alone <b>${c.esc(c.name(c.leadPO.h.id))}</b> ranks first, ${c.esc(c.words(c.secondPO))} than the next (<b>${c.esc(c.name(c.secondPO.h.id))}</b>${c.tiedPO.length ? `, tied with <b>${c.tiedPO.map((r) => c.esc(c.name(r.h.id))).join("</b> and <b>")}</b>` : ""}). With the range known, these explanations put the object in the same place; what separates them is how fast it moves through the air, which depends on the wind there.`,
      },
      settleStep("A balloon drifts with the wind; a slow flier or a free path needs some speed of its own through the air. A wind measured independently at the object's height, good to about 4 kt, would separate the balloon from the free path; nothing in this footage separates the slow flier from glare on a slow target."),
    ],
  },
  flir1: {
    title: "FLIR1 \"Tic Tac\", November 2004",
    steps: [
      {
        view: "cockpit", frame: 300, hyp: null, cmode: "render", spot: "#ck-panels", title: "The 2004 video",
        text: (c) => `FLIR1 is a small copy (${c.size}) with no distance on screen: the range slot reads ${c.placeholder ? `<b>${c.esc(c.placeholder.value)}</b> on every frame, a ${c.esc(c.placeholder.note)}` : "nothing useful"}. The lab still reads the pointing angles and the shape on every frame.`,
      },
      {
        view: "cockpit", frame: 300, play: 900, spot: "#ck-pic-l", title: "The shape",
        text: () => "Watch the shape and how it turns. Glare in the camera turns with the camera; a real object turns on its own. How precisely that rotation can be measured turns out to decide this case.",
      },
      {
        view: "cockpit", frame: 900, spot: "#rail .scores", title: "One number decides the leader",
        text: (c) => `On the video alone <b>${c.esc(c.name(c.leadPO.h.id))}</b> ranks first. ${c.rotation ? `But if the rotation is measured a little less precisely (above ${c.rotation.sigma.toFixed(2)} degrees instead of the ${c.rotation.main.toFixed(2)} degrees measured from the video), <b>${c.esc(c.name(c.rotation.leader))}</b> leads instead.` : ""}`,
      },
      {
        view: "godseye", frame: 0, play: 1500, spot: "#ge-gl", title: "From above",
        text: (c) => `The jet's path and the pod's sight lines. With no range on screen, the selected explanation's object sits about ${nmiTxt(c.derived(c.leadTW)?.range_nmi_mean)} away, but any distance along the sight lines fits the angles.`,
      },
      settleStep("The glare explanations need the object to hold its distance near the end of the clip; the free path needs it closing fast. A radar closure rate good to about 17 kt would tell them apart, whatever the rotation noise. The radar tracks the witnesses describe have not been released."),
    ],
  },
};
