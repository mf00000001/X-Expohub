<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
  images: string[]
  videoUrl?: string
}>()

const activeIndex = ref(0)
const showVideo = ref(false)
const brokenImages = ref<Set<number>>(new Set())
const videoError = ref(false)

const mainSrc = computed(() => {
  if (showVideo.value) return ''
  if (props.images.length === 0) return ''
  const idx = activeIndex.value
  if (idx >= props.images.length) return ''
  return props.images[idx]
})

const hasVideo = computed(() => !!props.videoUrl)

const videoEmbedUrl = computed(() => {
  if (!props.videoUrl) return ''
  const url = props.videoUrl
  // YouTube: convert watch / embed / youtu.be
  const ytWatch = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([\w-]+)/)
  if (ytWatch) return `https://www.youtube.com/embed/${ytWatch[1]}`
  // Vimeo
  const vimeoMatch = url.match(/vimeo\.com\/(\d+)/)
  if (vimeoMatch) return `https://player.vimeo.com/video/${vimeoMatch[1]}`
  // MP4 direct
  if (/\.mp4(\?|$)/i.test(url)) return url
  return url
})

const isVideoIframe = computed(() => {
  if (!props.videoUrl) return false
  return /youtube|youtu\.be|vimeo/i.test(props.videoUrl)
})

function selectImage(index: number) {
  if (brokenImages.value.has(index)) return
  activeIndex.value = index
  showVideo.value = false
}

function selectPrev() {
  if (props.images.length === 0) return
  showVideo.value = false
  activeIndex.value = (activeIndex.value - 1 + props.images.length) % props.images.length
}

function selectNext() {
  if (props.images.length === 0) return
  showVideo.value = false
  activeIndex.value = (activeIndex.value + 1) % props.images.length
}

function playVideo() {
  showVideo.value = true
}

function onImageError(index: number) {
  brokenImages.value = new Set([...brokenImages.value, index])
}

function onVideoError() {
  videoError.value = true
}
</script>

<template>
  <div class="image-gallery">
    <!-- Main display area -->
    <div class="gallery-main">
      <!-- Placeholder when no content -->
      <div v-if="images.length === 0 && !hasVideo" class="gallery-placeholder">
        <span class="placeholder-icon">&#128247;</span>
        <span class="placeholder-text">No images available</span>
      </div>

      <!-- Embedded video (iframe) -->
      <div
        v-else-if="showVideo && videoEmbedUrl && !videoError"
        class="gallery-video"
      >
        <iframe
          v-if="isVideoIframe"
          :src="videoEmbedUrl"
          class="video-iframe"
          frameborder="0"
          allow="autoplay; encrypted-media; picture-in-picture"
          allowfullscreen
          @error="onVideoError"
        ></iframe>
        <video
          v-else
          :src="videoEmbedUrl"
          class="video-player"
          controls
          autoplay
          @error="onVideoError"
        ></video>
        <button class="video-close-btn" @click="showVideo = false" title="Close video">
          &#10005;
        </button>
      </div>

      <!-- Image display -->
      <div v-else class="gallery-image-wrap">
        <!-- Broken image fallback -->
        <div
          v-if="!mainSrc || brokenImages.has(activeIndex)"
          class="gallery-broken"
        >
          <span class="broken-icon">&#128247;</span>
          <span class="broken-text">Image unavailable</span>
        </div>
        <img
          v-else
          :key="mainSrc"
          :src="mainSrc"
          :alt="'Product image ' + (activeIndex + 1)"
          class="gallery-img"
          @error="onImageError(activeIndex)"
        />

        <!-- Navigation arrows -->
        <button
          v-if="images.length > 1"
          class="nav-btn nav-prev"
          @click.stop="selectPrev"
          title="Previous"
        >&#10094;</button>
        <button
          v-if="images.length > 1"
          class="nav-btn nav-next"
          @click.stop="selectNext"
          title="Next"
        >&#10095;</button>

        <!-- Counter -->
        <span v-if="images.length > 1" class="gallery-counter">
          {{ activeIndex + 1 }} / {{ images.length }}
        </span>

        <!-- Play button overlay -->
        <button
          v-if="hasVideo && !showVideo"
          class="play-overlay"
          @click="playVideo"
          title="Play video"
        >
          <span class="play-icon">&#9654;</span>
        </button>
      </div>
    </div>

    <!-- Thumbnail strip -->
    <div v-if="images.length > 1 || hasVideo" class="gallery-thumbnails">
      <div
        v-for="(img, index) in images"
        :key="'thumb-' + index"
        class="thumbnail-item"
        :class="{ active: activeIndex === index && !showVideo }"
        @click="selectImage(index)"
      >
        <div
          v-if="brokenImages.has(index)"
          class="thumb-broken"
          title="Image unavailable"
        >&#128247;</div>
        <img
          v-else
          :src="img"
          :alt="'Thumbnail ' + (index + 1)"
          class="thumb-img"
          loading="lazy"
        />
      </div>

      <!-- Video thumbnail -->
      <div
        v-if="hasVideo"
        class="thumbnail-item video-thumb"
        :class="{ active: showVideo }"
        @click="playVideo"
        title="Play video"
      >
        <span class="video-thumb-icon">&#9654;</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.image-gallery {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ---- Main display ---- */
.gallery-main {
  position: relative;
  width: 100%;
  min-height: 350px;
  background: #f5f5f5;
  border-radius: 12px;
  overflow: hidden;
}

.gallery-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 350px;
  color: #bbb;
  gap: 8px;
}
.placeholder-icon { font-size: 60px; line-height: 1; }
.placeholder-text { font-size: 14px; }

.gallery-image-wrap {
  position: relative;
  width: 100%;
  min-height: 350px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.gallery-img {
  max-width: 100%;
  max-height: 450px;
  object-fit: contain;
}

.gallery-broken {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 350px;
  color: #ccc;
  gap: 8px;
}
.broken-icon { font-size: 56px; line-height: 1; }
.broken-text { font-size: 13px; }

/* Navigation */
.nav-btn {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: rgba(255,255,255,0.85);
  border: 1px solid #ddd;
  font-size: 18px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #333;
  transition: background 0.2s;
  z-index: 2;
}
.nav-btn:hover {
  background: rgba(255,255,255,1);
}
.nav-prev { left: 10px; }
.nav-next { right: 10px; }

.gallery-counter {
  position: absolute;
  bottom: 12px;
  right: 12px;
  background: rgba(0,0,0,0.55);
  color: #fff;
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 10px;
}

/* Play overlay */
.play-overlay {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: rgba(0,0,0,0.55);
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
  z-index: 3;
}
.play-overlay:hover {
  background: rgba(0,0,0,0.75);
}
.play-icon {
  color: #fff;
  font-size: 24px;
  margin-left: 3px;
}

/* Video embed */
.gallery-video {
  position: relative;
  width: 100%;
  padding-top: 56.25%; /* 16:9 */
  min-height: 350px;
}
.video-iframe,
.video-player {
  position: absolute;
  top: 0; left: 0;
  width: 100%;
  height: 100%;
  border: none;
  border-radius: 12px;
}
.video-close-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(0,0,0,0.6);
  color: #fff;
  border: none;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2;
}

/* ---- Thumbnail strip ---- */
.gallery-thumbnails {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 4px 0;
  scrollbar-width: thin;
}
.gallery-thumbnails::-webkit-scrollbar {
  height: 4px;
}
.gallery-thumbnails::-webkit-scrollbar-thumb {
  background: #ccc;
  border-radius: 4px;
}

.thumbnail-item {
  width: 70px;
  height: 70px;
  flex-shrink: 0;
  border-radius: 8px;
  overflow: hidden;
  border: 2px solid transparent;
  cursor: pointer;
  transition: border-color 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f5f5;
}
.thumbnail-item.active {
  border-color: #2563eb;
}
.thumbnail-item:hover {
  border-color: #93c5fd;
}

.thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.thumb-broken {
  font-size: 24px;
  color: #ccc;
}

.video-thumb {
  background: #1a1a2e;
}
.video-thumb-icon {
  color: #fff;
  font-size: 20px;
}
</style>
