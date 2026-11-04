// The lab's playback videos (/lab/data/video/*.mp4) use the same byte-range handler as the landing page clips,
// so Safari can play and seek them (see functions/media/[[path]].js).
export { onRequest } from "../../../media/[[path]].js";
