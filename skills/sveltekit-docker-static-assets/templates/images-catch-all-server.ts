// src/routes/images/[...path]/+server.ts
// Catch-all image serving route for SvelteKit Node adapter
// Serves files from static/images/ directory at runtime
// Handles both build-time images and runtime uploads

import { error } from '@sveltejs/kit'
import { readFile } from 'fs/promises'
import { join } from 'path'
import type { RequestHandler } from './$types'

const ALLOWED_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp', 'gif', 'svg']

export const GET: RequestHandler = async ({ params }) => {
	const { path } = params

	// Security: prevent directory traversal attacks
	if (path.includes('..') || path.includes('/./')) {
		throw error(400, 'Invalid path')
	}

	// Security: only allow image file extensions
	const ext = path.split('.').pop()?.toLowerCase()
	if (!ext || !ALLOWED_EXTENSIONS.includes(ext)) {
		throw error(403, 'File type not allowed')
	}

	try {
		// CRITICAL: Always use process.cwd() for Docker compatibility
		// Relative paths fail when cwd changes between dev and production
		const filePath = join(process.cwd(), 'static', 'images', path)
		const file = await readFile(filePath)

		// Map file extension to MIME type
		const contentType: Record<string, string> = {
			jpg: 'image/jpeg',
			jpeg: 'image/jpeg',
			png: 'image/png',
			webp: 'image/webp',
			gif: 'image/gif',
			svg: 'image/svg+xml'
		}

		return new Response(file, {
			headers: {
				'Content-Type': contentType[ext] || 'application/octet-stream',
				'Cache-Control': 'public, max-age=86400'  // 24h browser cache
			}
		})
	} catch (e) {
		// Log the error for debugging (optional)
		console.error(`Image not found: ${path}`, e)
		throw error(404, 'Image not found')
	}
}
