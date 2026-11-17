<template>
	<div ref="container" class="w-full" data-testid="pdf-viewer">
		<div v-if="error" class="py-16 text-center text-sm text-ink-red-3">
			{{ error }}
		</div>
		<div
			v-else-if="loading"
			class="py-16 text-center text-sm text-ink-gray-5"
		>
			{{ __('Loading document…') }}
		</div>
		<div
			v-for="page in pages"
			:key="page.number"
			:data-page="page.number"
			class="pdf-page mx-auto mb-3 w-full overflow-hidden rounded border border-outline-gray-2 bg-white shadow-sm"
			:style="{ aspectRatio: `${page.width} / ${page.height}` }"
		>
			<canvas class="block h-full w-full"></canvas>
		</div>
	</div>
</template>
<script setup>
/**
 * In-page PDF renderer.
 *
 * A plain <iframe src="x.pdf"> only works on desktop: Android Chrome offers a
 * download instead and iOS Safari shows just the first page. pdf.js draws
 * every page to a canvas, so documents read the same on every device.
 *
 * pdf.js is vendored under lms/public/pdfjs (prebuilt, Apache-2.0) and loaded
 * on demand, so it never lands in the main bundle or the lockfile.
 */
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const PDFJS_VERSION = '4.10.38'
const PDFJS_BASE = '/assets/lms/pdfjs'
// Pages this far outside the viewport are rendered ahead of time / kept.
const RENDER_MARGIN = '1000px 0px'

const props = defineProps({
	url: {
		type: String,
		required: true,
	},
})

const container = ref(null)
const pages = ref([])
const loading = ref(true)
const error = ref('')

let pdfjsPromise = null
let loadingTask = null
let pdfDocument = null
let observer = null
let generation = 0
const renderState = new Map() // page number -> { task, rendered }

const loadPdfjs = () => {
	if (!pdfjsPromise) {
		pdfjsPromise = import(
			/* @vite-ignore */ `${PDFJS_BASE}/pdf.min.js?v=${PDFJS_VERSION}`
		).then((lib) => {
			lib.GlobalWorkerOptions.workerSrc = `${PDFJS_BASE}/pdf.worker.min.js?v=${PDFJS_VERSION}`
			return lib
		})
	}
	return pdfjsPromise
}

const teardown = async () => {
	generation += 1
	observer?.disconnect()
	observer = null
	renderState.forEach((state) => state.task?.cancel?.())
	renderState.clear()
	pages.value = []
	const task = loadingTask
	loadingTask = null
	pdfDocument = null
	if (task) {
		try {
			await task.destroy()
		} catch (e) {
			// already destroyed
		}
	}
}

const renderPage = async (el, current) => {
	const number = Number(el.dataset.page)
	const state = renderState.get(number) || {}
	if (state.rendered || state.task || !pdfDocument) return
	renderState.set(number, state)
	try {
		const page = await pdfDocument.getPage(number)
		if (current !== generation) return
		const base = page.getViewport({ scale: 1 })
		const cssWidth = el.clientWidth || base.width
		const ratio = Math.min(window.devicePixelRatio || 1, 2)
		const viewport = page.getViewport({
			scale: (cssWidth / base.width) * ratio,
		})
		const canvas = el.querySelector('canvas')
		canvas.width = Math.floor(viewport.width)
		canvas.height = Math.floor(viewport.height)
		state.task = page.render({
			canvasContext: canvas.getContext('2d'),
			viewport,
		})
		await state.task.promise
		state.rendered = true
	} catch (e) {
		if (e?.name !== 'RenderingCancelledException') console.error(e)
	} finally {
		state.task = null
	}
}

const releasePage = (el) => {
	const number = Number(el.dataset.page)
	const state = renderState.get(number)
	if (!state) return
	state.task?.cancel?.()
	state.task = null
	if (state.rendered) {
		// Free the bitmap; long slide decks otherwise exhaust canvas memory
		// on phones. It is redrawn when the page scrolls back into range.
		const canvas = el.querySelector('canvas')
		canvas.width = 0
		canvas.height = 0
		state.rendered = false
	}
}

const load = async () => {
	await teardown()
	const current = generation
	loading.value = true
	error.value = ''
	try {
		const lib = await loadPdfjs()
		if (current !== generation) return
		loadingTask = lib.getDocument({
			url: props.url,
			withCredentials: true,
			disableRange: true,
			disableStream: true,
			isEvalSupported: false,
			standardFontDataUrl: `${PDFJS_BASE}/standard_fonts/`,
		})
		const doc = await loadingTask.promise
		if (current !== generation) return
		pdfDocument = doc

		const sizes = []
		for (let number = 1; number <= doc.numPages; number++) {
			const page = await doc.getPage(number)
			if (current !== generation) return
			const viewport = page.getViewport({ scale: 1 })
			sizes.push({ number, width: viewport.width, height: viewport.height })
		}
		pages.value = sizes
		loading.value = false
		await nextTick()
		if (current !== generation || !container.value) return

		observer = new IntersectionObserver(
			(entries) => {
				entries.forEach((entry) => {
					if (entry.isIntersecting) renderPage(entry.target, current)
					else releasePage(entry.target)
				})
			},
			{ rootMargin: RENDER_MARGIN }
		)
		container.value
			.querySelectorAll('.pdf-page')
			.forEach((el) => observer.observe(el))
	} catch (e) {
		if (current !== generation) return
		console.error(e)
		loading.value = false
		error.value = __('This document could not be displayed.')
	}
}

onMounted(load)
watch(() => props.url, load)
onBeforeUnmount(teardown)
</script>
