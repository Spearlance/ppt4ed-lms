<template>
	<div>
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs class="h-7" :items="breadcrumbs" />
			<Button variant="solid" @click="openCreate()">
				<template #prefix>
					<Plus class="h-4 w-4 stroke-1.5" />
				</template>
				{{
					currentParent
						? __('Add sub-category')
						: __('Add top-level category')
				}}
			</Button>
		</header>

		<div class="p-5">
			<div class="mb-4 max-w-3xl text-sm text-ink-gray-7">
				<template v-if="currentParent">
					{{ __('Sub-categories of') }}
					<span class="font-medium text-ink-gray-9">{{ currentParent }}</span>.
					{{ __('Click a folder to manage what is inside it.') }}
				</template>
				<template v-else>
					{{
						__(
							'Top-level categories. Click a folder to see what is inside, or add a new top-level category.'
						)
					}}
				</template>
			</div>

			<div v-if="children.loading && !children.data" class="text-sm text-ink-gray-5">
				{{ __('Loading…') }}
			</div>
			<div
				v-else-if="!children.data?.length"
				class="rounded border border-dashed p-8 text-center text-sm text-ink-gray-5"
			>
				<template v-if="currentParent">
					{{ __('No sub-categories under') }}
					<span class="font-medium">{{ currentParent }}</span>
					{{ __('yet.') }}
				</template>
				<template v-else>
					{{ __('No categories yet. Add one to get started.') }}
				</template>
			</div>
			<div
				v-else
				class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3"
			>
				<div
					v-for="node in children.data"
					:key="node.name"
					class="group flex items-center gap-3 rounded-md border bg-surface-white p-3 hover:border-outline-gray-3 hover:bg-surface-gray-1 transition-colors"
				>
					<button
						class="flex min-w-0 flex-1 items-center gap-3 text-left"
						@click="enterFolder(node.name)"
					>
						<Folder class="h-5 w-5 shrink-0 text-ink-amber-3" />
						<div class="min-w-0 flex-1">
							<div class="truncate text-sm font-medium text-ink-gray-9">
								{{ node.label }}
							</div>
							<div class="text-xs text-ink-gray-5">
								{{ node.subtree_resource_count }}
								{{
									node.subtree_resource_count === 1
										? __('resource')
										: __('resources')
								}}
							</div>
						</div>
					</button>
					<div class="flex shrink-0 items-center gap-1 opacity-0 group-hover:opacity-100">
						<Button
							size="sm"
							variant="ghost"
							:aria-label="__('Add sub-category')"
							@click.stop="openCreate(node)"
						>
							<template #icon><Plus class="h-3.5 w-3.5" /></template>
						</Button>
						<Button
							size="sm"
							variant="ghost"
							:aria-label="__('Rename')"
							@click.stop="openRename(node)"
						>
							<template #icon><Pencil class="h-3.5 w-3.5" /></template>
						</Button>
						<Button
							size="sm"
							variant="ghost"
							:aria-label="__('Move')"
							@click.stop="openMove(node)"
						>
							<template #icon><Move class="h-3.5 w-3.5" /></template>
						</Button>
						<Button
							size="sm"
							variant="ghost"
							theme="red"
							:aria-label="__('Delete')"
							@click.stop="openDelete(node)"
						>
							<template #icon><Trash2 class="h-3.5 w-3.5" /></template>
						</Button>
					</div>
				</div>
			</div>
		</div>

		<!-- Create -->
		<Dialog
			v-model="createDialog.show"
			:options="{
				title: createDialog.parent
					? __('Add sub-category under') + ' ' + createDialog.parentLabel
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
			:options="{ title: __('Move') + ' ' + moveDialog.label }"
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
					<option v-for="opt in moveOptions" :key="opt.name" :value="opt.name">
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
				title: __('Delete') + ' ' + deleteDialog.label + '?',
			}"
		>
			<template #body-content>
				<div v-if="deleteDialog.confirm" class="space-y-2 text-sm">
					<p class="text-ink-red-3">
						{{
							__('This category contains') +
							' ' +
							deleteDialog.confirm.child_count +
							' ' +
							__('sub-categories and') +
							' ' +
							deleteDialog.confirm.resource_count +
							' ' +
							__('resources.')
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
import {
	Breadcrumbs,
	Button,
	Dialog,
	FormControl,
	createResource,
	toast,
	usePageMeta,
} from 'frappe-ui'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Folder, Move, Pencil, Plus, Trash2 } from 'lucide-vue-next'
import { cleanError } from '@/utils'

usePageMeta(() => ({ title: 'Categories' }))

const route = useRoute()
const router = useRouter()
const currentParent = ref(route.query.parent || null)
const ancestorTrail = ref([])

// Direct children of the current folder (or top level if currentParent is null).
const children = createResource({
	url: 'lms.lms.api.get_category_children',
	params: { parent: currentParent.value },
	auto: true,
})

const breadcrumbsResource = createResource({
	url: 'lms.lms.api.get_category_breadcrumbs',
	params: { name: currentParent.value || '' },
	onSuccess(data) {
		ancestorTrail.value = data || []
	},
})

// Full tree, used only for the Move dialog's parent picker.
const fullTree = createResource({
	url: 'lms.lms.api.get_category_tree',
	auto: true,
})

const reloadAll = () => {
	children.update({ params: { parent: currentParent.value || null } })
	children.reload()
	if (currentParent.value) {
		breadcrumbsResource.update({ params: { name: currentParent.value } })
		breadcrumbsResource.reload()
	} else {
		ancestorTrail.value = []
	}
	fullTree.reload()
}

const enterFolder = (name) => {
	router.push({
		name: 'AdminCategories',
		query: { ...route.query, parent: name },
	})
}

watch(
	() => route.query.parent,
	(val) => {
		const next = val || null
		if (next !== currentParent.value) {
			currentParent.value = next
			reloadAll()
		}
	}
)

onMounted(() => reloadAll())

const breadcrumbs = computed(() => {
	const items = [
		{
			label: __('Categories'),
			route: { name: 'AdminCategories' },
		},
	]
	for (const crumb of ancestorTrail.value) {
		items.push({
			label: crumb.label,
			route: { name: 'AdminCategories', query: { parent: crumb.name } },
		})
	}
	return items
})

// ── Create ─────────────────────────────────────────────────────────────
const createDialog = reactive({ show: false, parent: null, parentLabel: '', label: '' })
const openCreate = (parentNode = null) => {
	// If called without a node arg, "Add" at the page level — adds under
	// the current folder (or top-level if at root).
	if (parentNode) {
		createDialog.parent = parentNode.name
		createDialog.parentLabel = parentNode.label
	} else {
		createDialog.parent = currentParent.value || null
		createDialog.parentLabel = currentParent.value || ''
	}
	createDialog.label = ''
	createDialog.show = true
}
const createCall = createResource({
	url: 'lms.lms.api.create_category',
	onSuccess() {
		toast.success(__('Category created'))
		createDialog.show = false
		reloadAll()
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
	onSuccess(data) {
		toast.success(__('Category renamed'))
		renameDialog.show = false
		// If we renamed the folder we're currently inside, update the URL.
		if (data?.name && renameDialog.name === currentParent.value) {
			router.replace({
				name: 'AdminCategories',
				query: { ...route.query, parent: data.name },
			})
		} else {
			reloadAll()
		}
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
	moveDialog.newParent = currentParent.value || null
	moveDialog.show = true
}
const flatTreePaths = computed(() => {
	const out = []
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
	const walk = (nodes, trail) => {
		for (const n of nodes || []) {
			const path = trail.concat(n.label).join(' › ')
			out.push({ name: n.name, path, descendants: collectDescendants(n) })
			walk(n.children, trail.concat(n.label))
		}
	}
	walk(fullTree.data || [], [])
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
		reloadAll()
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
			deleteDialog.confirm = data
			return
		}
		toast.success(__('Category deleted'))
		deleteDialog.show = false
		reloadAll()
	},
	onError(err) {
		toast.error(cleanError(err.messages?.[0]) || __('Could not delete'))
	},
})
const submitDelete = () => {
	const force = deleteDialog.confirm ? 1 : 0
	deleteCall.submit({ name: deleteDialog.name, force })
}
</script>
