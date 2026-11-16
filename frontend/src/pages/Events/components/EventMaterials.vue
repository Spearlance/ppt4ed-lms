<template>
	<div class="p-5" data-testid="event-materials">
		<div class="grid grid-cols-1 gap-5 lg:grid-cols-[20rem,1fr]">
			<!-- List -->
			<div :class="selected ? 'hidden lg:block' : ''">
				<div class="mb-4 flex items-center justify-between gap-3">
					<div class="text-lg font-semibold text-ink-gray-9">
						{{ __('Materials') }}
					</div>
					<Button v-if="canManage" variant="solid" @click="openAddDialog">
						<template #prefix>
							<Plus class="size-4 stroke-1.5" />
						</template>
						{{ __('Add material') }}
					</Button>
				</div>

				<div
					v-if="materials.loading && !materials.data"
					class="text-sm text-ink-gray-5"
				>
					{{ __('Loading…') }}
				</div>
				<div
					v-else-if="!rows.length"
					class="rounded-lg border border-dashed border-outline-gray-2 p-6 text-center text-sm text-ink-gray-6"
				>
					{{
						canManage
							? __(
									'No materials yet. Add handouts, slides or forms for your attendees.'
							  )
							: __('No materials have been added to this event yet.')
					}}
				</div>
				<ul v-else class="space-y-2">
					<li
						v-for="(row, index) in rows"
						:key="row.name"
						class="flex items-center gap-1 rounded-lg border p-1"
						:class="
							selected?.name === row.name
								? 'border-outline-gray-4 bg-surface-gray-2'
								: 'border-outline-gray-2 hover:bg-surface-gray-1'
						"
						data-testid="material-row"
					>
						<button
							type="button"
							class="flex min-w-0 flex-1 items-center gap-3 rounded-md p-2 text-left"
							@click="select(row)"
						>
							<component
								:is="row.file_type === 'image' ? ImageIcon : FileText"
								class="size-5 shrink-0 stroke-1.5 text-ink-gray-6"
							/>
							<span class="min-w-0 flex-1">
								<span
									class="block truncate text-base font-medium text-ink-gray-9"
								>
									{{ row.title }}
								</span>
								<span class="block text-xs uppercase text-ink-gray-5">
									{{ row.extension }}
								</span>
							</span>
						</button>
						<div v-if="canManage" class="flex shrink-0 items-center pr-1">
							<button
								type="button"
								class="rounded p-1.5 text-ink-gray-6 hover:bg-surface-gray-3 disabled:opacity-30"
								:aria-label="__('Move up')"
								:title="__('Move up')"
								:disabled="index === 0"
								@click="move(index, -1)"
							>
								<ChevronUp class="size-4 stroke-1.5" />
							</button>
							<button
								type="button"
								class="rounded p-1.5 text-ink-gray-6 hover:bg-surface-gray-3 disabled:opacity-30"
								:aria-label="__('Move down')"
								:title="__('Move down')"
								:disabled="index === rows.length - 1"
								@click="move(index, 1)"
							>
								<ChevronDown class="size-4 stroke-1.5" />
							</button>
							<button
								type="button"
								class="rounded p-1.5 text-ink-gray-6 hover:bg-surface-gray-3"
								:aria-label="__('Rename')"
								:title="__('Rename')"
								@click="openRenameDialog(row)"
							>
								<Pencil class="size-4 stroke-1.5" />
							</button>
							<button
								type="button"
								class="rounded p-1.5 text-ink-red-3 hover:bg-surface-gray-3"
								:aria-label="__('Delete')"
								:title="__('Delete')"
								@click="openDeleteDialog(row)"
							>
								<Trash2 class="size-4 stroke-1.5" />
							</button>
						</div>
					</li>
				</ul>
			</div>

			<!-- Viewer -->
			<div v-if="selected" class="min-w-0" data-testid="material-viewer">
				<div class="mb-4 flex items-center justify-between gap-3">
					<div class="flex min-w-0 items-center gap-2">
						<button
							type="button"
							class="rounded p-1.5 text-ink-gray-7 hover:bg-surface-gray-2 lg:hidden"
							:aria-label="__('Back to materials')"
							@click="selected = null"
						>
							<ArrowLeft class="size-5 stroke-1.5" />
						</button>
						<div class="truncate text-lg font-semibold text-ink-gray-9">
							{{ selected.title }}
						</div>
					</div>
					<a
						:href="fileUrl(selected, true)"
						class="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-outline-gray-2 px-2.5 py-1.5 text-sm text-ink-gray-8 hover:bg-surface-gray-2"
					>
						<Download class="size-4 stroke-1.5" />
						{{ __('Download') }}
					</a>
				</div>
				<div class="rounded-lg bg-surface-gray-2 p-2 sm:p-4">
					<PdfViewer
						v-if="selected.file_type === 'pdf'"
						:key="selected.name"
						:url="fileUrl(selected)"
						class="mx-auto max-w-4xl"
					/>
					<img
						v-else-if="selected.file_type === 'image'"
						:src="fileUrl(selected)"
						:alt="selected.title"
						class="mx-auto block h-auto max-w-full rounded border border-outline-gray-2 bg-white"
					/>
					<div v-else class="py-16 text-center text-sm text-ink-gray-6">
						{{ __('This file type cannot be previewed.') }}
					</div>
				</div>
			</div>
			<div
				v-else-if="rows.length"
				class="hidden items-center justify-center rounded-lg bg-surface-gray-1 p-10 text-sm text-ink-gray-5 lg:flex"
			>
				{{ __('Select a material to view it.') }}
			</div>
		</div>

		<!-- Add -->
		<Dialog
			v-model="showAddDialog"
			:options="{
				title: __('Add material'),
				size: 'lg',
				actions: [
					{
						label: __('Add'),
						variant: 'solid',
						disabled: !draft.file || !draft.title.trim(),
						loading: saving,
						onClick: (close) => addMaterial(close),
					},
				],
			}"
		>
			<template #body-content>
				<div class="flex flex-col gap-4">
					<FormControl
						:label="__('Name')"
						type="text"
						v-model="draft.title"
						:placeholder="__('e.g. Course slides')"
						:required="true"
						data-testid="material-title-input"
					/>
					<div>
						<div class="mb-1.5 text-xs text-ink-gray-5">
							{{ __('File') }}
							<span class="text-ink-red-3">*</span>
						</div>
						<FileUploader
							:fileTypes="ACCEPT"
							:uploadArgs="{ private: true }"
							:validateFile="validateMaterialFile"
							@success="onUploaded"
							@failure="onUploadFailure"
						>
							<template #default="{ progress, uploading, openFileSelector }">
								<div class="flex items-center gap-3">
									<Button @click="openFileSelector" :loading="uploading">
										{{
											uploading
												? `${__('Uploading')} ${progress}%`
												: draft.file
												? __('Replace file')
												: __('Choose file')
										}}
									</Button>
									<span
										v-if="draft.file"
										class="truncate text-sm text-ink-gray-7"
										data-testid="material-uploaded-name"
									>
										{{ draft.fileName }}
									</span>
								</div>
							</template>
						</FileUploader>
						<p class="mt-2 text-xs text-ink-gray-5">
							{{
								__(
									'PDF, PNG, JPG or GIF, up to 25 MB. Only registered attendees can open it.'
								)
							}}
						</p>
					</div>
				</div>
			</template>
		</Dialog>

		<!-- Rename -->
		<Dialog
			v-model="showRenameDialog"
			:options="{
				title: __('Rename material'),
				actions: [
					{
						label: __('Save'),
						variant: 'solid',
						disabled: !renameTitle.trim(),
						loading: saving,
						onClick: (close) => renameMaterial(close),
					},
				],
			}"
		>
			<template #body-content>
				<FormControl
					:label="__('Name')"
					type="text"
					v-model="renameTitle"
					:required="true"
				/>
			</template>
		</Dialog>

		<!-- Delete -->
		<Dialog
			v-model="showDeleteDialog"
			:options="{
				title: __('Delete material'),
				message: __(
					'Attendees will no longer be able to open “{0}”. This cannot be undone.'
				).format(target?.title || ''),
				actions: [
					{
						label: __('Delete'),
						variant: 'solid',
						theme: 'red',
						loading: saving,
						onClick: (close) => deleteMaterial(close),
					},
				],
			}"
		/>
	</div>
</template>
<script setup>
import { computed, reactive, ref, watch } from 'vue'
import {
	Button,
	Dialog,
	FileUploader,
	FormControl,
	call,
	createResource,
	toast,
} from 'frappe-ui'
import {
	ArrowLeft,
	ChevronDown,
	ChevronUp,
	Download,
	FileText,
	Image as ImageIcon,
	Pencil,
	Plus,
	Trash2,
} from 'lucide-vue-next'
import PdfViewer from '@/components/PdfViewer.vue'
import { usersStore } from '@/stores/user'

const API = 'lms.lms.event_materials'
const ACCEPT = '.pdf,.png,.jpg,.jpeg,.gif'
const ALLOWED_EXTENSIONS = ['pdf', 'png', 'jpg', 'jpeg', 'gif']
const MAX_BYTES = 25 * 1024 * 1024

const props = defineProps({
	batch: {
		type: Object,
		default: null,
	},
})

const { userResource } = usersStore()

const eventName = computed(() => props.batch?.data?.name)

const canManage = computed(() => {
	if (window.read_only_mode) return false
	const user = userResource.data
	if (!user) return false
	if (user.is_moderator) return true
	return Boolean(
		props.batch?.data?.instructors?.some((i) => i.name === user.name)
	)
})

const selected = ref(null)
const saving = ref(false)

const materials = createResource({
	url: `${API}.get_event_materials`,
	makeParams: () => ({ event: eventName.value }),
	onSuccess: (data) => {
		if (selected.value) {
			// keep the open material in sync after a rename / delete
			selected.value =
				data.find((row) => row.name === selected.value.name) || null
		}
		// On desktop the viewer sits beside the list, so open the first
		// material straight away. On phones the list comes first.
		if (!selected.value && data.length && window.innerWidth >= 1024) {
			selected.value = data[0]
		}
	},
})

watch(
	eventName,
	(name) => {
		if (name) materials.reload()
	},
	{ immediate: true }
)

const rows = computed(() => materials.data || [])

const fileUrl = (row, download = false) =>
	`/api/method/${API}.view_event_material?name=${encodeURIComponent(
		row.name
	)}${download ? '&download=1' : ''}`

const select = (row) => {
	selected.value = row
}

const errorMessage = (error) => {
	if (error?.messages?.length) return error.messages[0]
	if (error?._server_messages) {
		try {
			return JSON.parse(JSON.parse(error._server_messages)[0]).message
		} catch (e) {
			// fall through
		}
	}
	return error?.message || __('Something went wrong. Please try again.')
}

// ---------------------------------------------------------------- add

const showAddDialog = ref(false)
const draft = reactive({ title: '', file: '', fileName: '' })

const openAddDialog = () => {
	draft.title = ''
	draft.file = ''
	draft.fileName = ''
	showAddDialog.value = true
}

const validateMaterialFile = (file) => {
	const extension = file.name.split('.').pop().toLowerCase()
	let message = ''
	if (!ALLOWED_EXTENSIONS.includes(extension)) {
		message = __('Only PDF, PNG, JPG and GIF files can be added.')
	} else if (file.size > MAX_BYTES) {
		message = __('This file is larger than 25 MB.')
	}
	if (message) toast.error(message)
	return message
}

const onUploaded = (file) => {
	draft.file = file.name
	draft.fileName = file.file_name
	if (!draft.title.trim()) {
		// Suggest a readable name from the filename; the admin can edit it.
		draft.title = (file.file_name || '')
			.replace(/\.[^.]+$/, '')
			.replace(/[_]+/g, ' ')
			.trim()
	}
}

const onUploadFailure = (error) => {
	toast.error(errorMessage(error))
}

const addMaterial = async (close) => {
	saving.value = true
	try {
		const row = await call(`${API}.add_event_material`, {
			event: eventName.value,
			title: draft.title,
			file: draft.file,
		})
		toast.success(__('Material added'))
		close()
		selected.value = row
		await materials.reload()
		// lets the Materials tab / dashboard banner appear for attendees
		props.batch?.reload?.()
	} catch (error) {
		toast.error(errorMessage(error))
	} finally {
		saving.value = false
	}
}

// ---------------------------------------------------------------- rename

const showRenameDialog = ref(false)
const renameTitle = ref('')
const target = ref(null)

const openRenameDialog = (row) => {
	target.value = row
	renameTitle.value = row.title
	showRenameDialog.value = true
}

const renameMaterial = async (close) => {
	saving.value = true
	try {
		await call(`${API}.rename_event_material`, {
			name: target.value.name,
			title: renameTitle.value,
		})
		toast.success(__('Material renamed'))
		close()
		await materials.reload()
	} catch (error) {
		toast.error(errorMessage(error))
	} finally {
		saving.value = false
	}
}

// ---------------------------------------------------------------- delete

const showDeleteDialog = ref(false)

const openDeleteDialog = (row) => {
	target.value = row
	showDeleteDialog.value = true
}

const deleteMaterial = async (close) => {
	saving.value = true
	try {
		await call(`${API}.delete_event_material`, { name: target.value.name })
		toast.success(__('Material deleted'))
		close()
		await materials.reload()
		props.batch?.reload?.()
	} catch (error) {
		toast.error(errorMessage(error))
	} finally {
		saving.value = false
	}
}

// ---------------------------------------------------------------- reorder

const move = async (index, direction) => {
	const order = rows.value.map((row) => row.name)
	const swapWith = index + direction
	if (swapWith < 0 || swapWith >= order.length) return
	;[order[index], order[swapWith]] = [order[swapWith], order[index]]
	try {
		const data = await call(`${API}.reorder_event_materials`, {
			event: eventName.value,
			names: order,
		})
		materials.setData(data)
	} catch (error) {
		toast.error(errorMessage(error))
	}
}
</script>
