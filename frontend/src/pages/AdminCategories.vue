<template>
	<div>
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs
				class="h-7"
				:items="[
					{
						label: __('Categories'),
						route: { name: 'AdminCategories' },
					},
				]"
			/>
			<Button variant="solid" @click="openCreate(null)">
				<template #prefix>
					<Plus class="h-4 w-4 stroke-1.5" />
				</template>
				{{ __('Add top-level category') }}
			</Button>
		</header>

		<div class="p-5">
			<div class="mb-4 max-w-3xl text-sm text-ink-gray-7">
				{{
					__(
						'Categories are folders that organize resources. Nest them as deep as you like — for example, “Parent Resources › Social Stories › Daily Routines”. Renaming a category automatically updates every resource that uses it.'
					)
				}}
			</div>

			<div v-if="tree.loading && !tree.data" class="text-sm text-ink-gray-5">
				{{ __('Loading…') }}
			</div>
			<div
				v-else-if="!tree.data?.length"
				class="rounded border border-dashed p-8 text-center text-sm text-ink-gray-5"
			>
				{{ __('No categories yet. Add one to get started.') }}
			</div>
			<div v-else class="max-w-3xl rounded border bg-surface-white">
				<CategoryNode
					v-for="node in tree.data"
					:key="node.name"
					:node="node"
					:depth="0"
					:expanded="expanded"
					@toggle="toggle"
					@add-child="openCreate"
					@rename="openRename"
					@move="openMove"
					@delete="openDelete"
				/>
			</div>
		</div>

		<!-- Create -->
		<Dialog
			v-model="createDialog.show"
			:options="{
				title: createDialog.parent
					? __('Add sub-category under {0}').replace('{0}', createDialog.parentLabel)
					: __('Add top-level category'),
			}"
		>
			<template #body-content>
				<FormControl
					v-model="createDialog.label"
					:label="__('Name')"
					:required="true"
					autocomplete="off"
					@keyup.enter="submitCreate"
				/>
			</template>
			<template #actions="{ close }">
				<div class="space-x-2 text-right">
					<Button @click="close">{{ __('Cancel') }}</Button>
					<Button variant="solid" :loading="createCall.loading" @click="submitCreate">
						{{ __('Create') }}
					</Button>
				</div>
			</template>
		</Dialog>

		<!-- Rename -->
		<Dialog v-model="renameDialog.show" :options="{ title: __('Rename category') }">
			<template #body-content>
				<FormControl
					v-model="renameDialog.label"
					:label="__('New name')"
					:required="true"
					autocomplete="off"
					@keyup.enter="submitRename"
				/>
				<div class="mt-2 text-xs text-ink-gray-5">
					{{
						__(
							'Resources using this category will pick up the new name automatically.'
						)
					}}
				</div>
			</template>
			<template #actions="{ close }">
				<div class="space-x-2 text-right">
					<Button @click="close">{{ __('Cancel') }}</Button>
					<Button variant="solid" :loading="renameCall.loading" @click="submitRename">
						{{ __('Rename') }}
					</Button>
				</div>
			</template>
		</Dialog>

		<!-- Move -->
		<Dialog
			v-model="moveDialog.show"
			:options="{
				title: __('Move {0}').replace('{0}', moveDialog.label),
			}"
		>
			<template #body-content>
				<div class="mb-2 text-sm text-ink-gray-7">
					{{ __('Pick a new parent. Leave blank to move to the top level.') }}
				</div>
				<select
					v-model="moveDialog.newParent"
					class="w-full rounded border border-outline-gray-modals bg-surface-white px-2 py-1.5 text-sm"
				>
					<option :value="null">— {{ __('Top level') }} —</option>
					<option
						v-for="opt in moveOptions"
						:key="opt.name"
						:value="opt.name"
					>
						{{ opt.path }}
					</option>
				</select>
			</template>
			<template #actions="{ close }">
				<div class="space-x-2 text-right">
					<Button @click="close">{{ __('Cancel') }}</Button>
					<Button variant="solid" :loading="moveCall.loading" @click="submitMove">
						{{ __('Move') }}
					</Button>
				</div>
			</template>
		</Dialog>

		<!-- Delete -->
		<Dialog
			v-model="deleteDialog.show"
			:options="{
				title: __('Delete {0}?').replace('{0}', deleteDialog.label),
			}"
		>
			<template #body-content>
				<div v-if="deleteDialog.confirm" class="space-y-2 text-sm">
					<p class="text-ink-red-3">
						{{
							__(
								'This category contains {0} sub-categories and {1} resources.'
							)
								.replace('{0}', deleteDialog.confirm.child_count)
								.replace('{1}', deleteDialog.confirm.resource_count)
						}}
					</p>
					<p class="text-ink-gray-7">
						{{
							__(
								'Deleting will remove the sub-categories and unset the category on every resource inside (resources themselves are kept).'
							)
						}}
					</p>
				</div>
				<div v-else class="text-sm text-ink-gray-7">
					{{ __('This category is empty. Delete it?') }}
				</div>
			</template>
			<template #actions="{ close }">
				<div class="space-x-2 text-right">
					<Button @click="close">{{ __('Cancel') }}</Button>
					<Button
						theme="red"
						variant="solid"
						:loading="deleteCall.loading"
						@click="submitDelete"
					>
						{{ __('Delete') }}
					</Button>
				</div>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import { Breadcrumbs, Button, Dialog, FormControl, createResource, toast, usePageMeta } from 'frappe-ui'
import { computed, onMounted, reactive, ref } from 'vue'
import { Plus } from 'lucide-vue-next'
import CategoryNode from '@/pages/AdminCategories/CategoryNode.vue'
import { cleanError } from '@/utils'

usePageMeta({ title: 'Categories' })

const expanded = ref(new Set())
const toggle = (name) => {
	if (expanded.value.has(name)) expanded.value.delete(name)
	else expanded.value.add(name)
	expanded.value = new Set(expanded.value)
}

const tree = createResource({
	url: 'lms.lms.api.get_category_tree',
	auto: true,
	onSuccess(data) {
		// Auto-expand the first two levels on first load for orientation.
		if (expanded.value.size === 0) {
			const expandFirstTwo = (nodes, depth = 0) => {
				if (depth >= 2) return
				for (const n of nodes) {
					if (n.children?.length) {
						expanded.value.add(n.name)
						expandFirstTwo(n.children, depth + 1)
					}
				}
			}
			expandFirstTwo(data || [])
			expanded.value = new Set(expanded.value)
		}
	},
})

const reload = () => tree.reload()

// ── Create ─────────────────────────────────────────────────────────────
const createDialog = reactive({ show: false, parent: null, parentLabel: '', label: '' })
const openCreate = (parentNode) => {
	createDialog.parent = parentNode?.name || null
	createDialog.parentLabel = parentNode?.label || ''
	createDialog.label = ''
	createDialog.show = true
}
const createCall = createResource({
	url: 'lms.lms.api.create_category',
	onSuccess(data) {
		toast.success(__('Category created'))
		createDialog.show = false
		if (data?.parent) expanded.value.add(data.parent)
		expanded.value = new Set(expanded.value)
		reload()
	},
	onError(err) {
		toast.error(cleanError(err.messages?.[0]) || __('Could not create category'))
	},
})
const submitCreate = () => {
	const label = createDialog.label?.trim()
	if (!label) return
	createCall.submit({ label, parent: createDialog.parent || null })
}

// ── Rename ─────────────────────────────────────────────────────────────
const renameDialog = reactive({ show: false, name: '', label: '' })
const openRename = (node) => {
	renameDialog.name = node.name
	renameDialog.label = node.label
	renameDialog.show = true
}
const renameCall = createResource({
	url: 'lms.lms.api.rename_category',
	onSuccess() {
		toast.success(__('Category renamed'))
		renameDialog.show = false
		reload()
	},
	onError(err) {
		toast.error(cleanError(err.messages?.[0]) || __('Could not rename'))
	},
})
const submitRename = () => {
	const label = renameDialog.label?.trim()
	if (!label || label === renameDialog.name) {
		renameDialog.show = false
		return
	}
	renameCall.submit({ name: renameDialog.name, new_label: label })
}

// ── Move ───────────────────────────────────────────────────────────────
const moveDialog = reactive({ show: false, name: '', label: '', newParent: null })
const openMove = (node) => {
	moveDialog.name = node.name
	moveDialog.label = node.label
	moveDialog.newParent = node.parent || null
	moveDialog.show = true
}
const flatTreePaths = computed(() => {
	const out = []
	const walk = (nodes, trail) => {
		for (const n of nodes || []) {
			const path = trail.concat(n.label).join(' › ')
			out.push({ name: n.name, path, descendants: collectDescendants(n) })
			walk(n.children, trail.concat(n.label))
		}
	}
	const collectDescendants = (n) => {
		const set = new Set([n.name])
		const stack = [...(n.children || [])]
		while (stack.length) {
			const c = stack.pop()
			set.add(c.name)
			if (c.children) stack.push(...c.children)
		}
		return set
	}
	walk(tree.data || [], [])
	return out
})
const moveOptions = computed(() => {
	if (!moveDialog.name) return []
	const selfEntry = flatTreePaths.value.find((e) => e.name === moveDialog.name)
	const forbidden = selfEntry ? selfEntry.descendants : new Set()
	return flatTreePaths.value.filter((e) => !forbidden.has(e.name))
})
const moveCall = createResource({
	url: 'lms.lms.api.move_category',
	onSuccess() {
		toast.success(__('Category moved'))
		moveDialog.show = false
		reload()
	},
	onError(err) {
		toast.error(cleanError(err.messages?.[0]) || __('Could not move'))
	},
})
const submitMove = () => {
	moveCall.submit({ name: moveDialog.name, new_parent: moveDialog.newParent || null })
}

// ── Delete ─────────────────────────────────────────────────────────────
const deleteDialog = reactive({ show: false, name: '', label: '', confirm: null })
const openDelete = (node) => {
	deleteDialog.name = node.name
	deleteDialog.label = node.label
	deleteDialog.confirm = null
	deleteDialog.show = true
}
const deleteCall = createResource({
	url: 'lms.lms.api.delete_category',
	onSuccess(data) {
		if (data?.requires_force) {
			// Server says it's non-empty — re-render dialog body with the counts so
			// the user knows what they're about to nuke before they confirm.
			deleteDialog.confirm = data
			return
		}
		toast.success(__('Category deleted'))
		deleteDialog.show = false
		reload()
	},
	onError(err) {
		toast.error(cleanError(err.messages?.[0]) || __('Could not delete'))
	},
})
const submitDelete = () => {
	const force = deleteDialog.confirm ? 1 : 0
	deleteCall.submit({ name: deleteDialog.name, force })
}

onMounted(() => reload())
</script>
