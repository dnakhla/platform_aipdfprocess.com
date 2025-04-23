# PDF Processing Functions Specification

## Core Function Design

Each PDF processing function follows a consistent design pattern:

```javascript
/**
 * PDF Processing Lambda Handler
 * 
 * @param {Object} event - Lambda event object
 * @param {string} event.bucketName - S3 bucket containing the PDF
 * @param {string} event.key - S3 key for the input PDF file
 * @param {string} event.outputBucket - S3 bucket for processed output
 * @param {string} event.outputKey - S3 key for the output file
 * @param {Object} event.parameters - Tool-specific parameters
 * @param {string} event.jobId - Unique job identifier
 * @param {Context} context - Lambda context
 * @returns {Object} Processing result with metadata
 */
exports.handler = async (event, context) => {
  try {
    // 1. Download PDF from S3
    // 2. Process according to function purpose
    // 3. Upload result to S3
    // 4. Return processing metadata
    return {
      success: true,
      outputBucket: event.outputBucket,
      outputKey: event.outputKey,
      metadata: {
        // Function-specific metadata
      }
    };
  } catch (error) {
    console.error('Processing error:', error);
    return {
      success: false,
      error: error.message,
      errorDetails: error.stack
    };
  }
};
```

## Function Specifications

### 1. Resize PDF (`aipdf-processing-resize`)

```yaml
Name: aipdf-processing-resize
Description: Resizes PDF pages by scaling or changing dimensions
Runtime: nodejs16.x
Memory: 512MB
Timeout: 30s
Parameters:
  - scale: number (Scale factor, e.g., 0.5 for half size)
  - width: number (Target width in points)
  - height: number (Target height in points)
  - preserveAspectRatio: boolean (Default: true)
  - pages: array[number] (Specific pages to resize, empty for all)
Dependencies: 
  - pdf-lib
  - sharp
Output: Resized PDF file
```

### 2. Extract Text (`aipdf-processing-extract-text`)

```yaml
Name: aipdf-processing-extract-text
Description: Extracts text content from PDF pages
Runtime: nodejs16.x
Memory: 1024MB
Timeout: 60s
Parameters:
  - useOcr: boolean (Whether to use OCR if text extraction fails)
  - pages: array[number] (Specific pages to extract text from, empty for all)
  - includeLayout: boolean (Whether to preserve text layout information)
  - outputFormat: string (Format of extracted text - plain, markdown, json)
Dependencies:
  - pdf-lib
  - pdfjs-dist
  - tesseract.js (for OCR)
Output: Text file (format depends on outputFormat parameter)
```

### 3. Extract Images (`aipdf-processing-extract-images`)

```yaml
Name: aipdf-processing-extract-images
Description: Extracts embedded images from PDF pages
Runtime: nodejs16.x
Memory: 1024MB
Timeout: 60s
Parameters:
  - minWidth: number (Minimum width to extract)
  - minHeight: number (Minimum height to extract)
  - pages: array[number] (Specific pages to extract from, empty for all)
  - format: string (Output image format - png, jpeg, webp)
  - quality: number (Image quality for lossy formats)
Dependencies:
  - pdf-lib
  - pdfjs-dist
  - sharp
Output: ZIP file containing extracted images
```

### 4. Page as Image (`aipdf-processing-page-as-image`)

```yaml
Name: aipdf-processing-page-as-image
Description: Renders PDF pages as high-quality images
Runtime: nodejs16.x
Memory: 1024MB
Timeout: 45s
Parameters:
  - dpi: number (Resolution in DPI, default 150)
  - pages: array[number] (Specific pages to render, empty for all)
  - format: string (Output image format - png, jpeg, webp)
  - quality: number (Image quality for lossy formats)
  - transparent: boolean (For PNG, whether to preserve transparency)
Dependencies:
  - pdf-lib
  - sharp
  - ghostscript (via layer)
Output: ZIP file containing page images or single image for one page
```

### 5. Compress PDF (`aipdf-processing-compress`)

```yaml
Name: aipdf-processing-compress
Description: Reduces PDF file size by optimizing content
Runtime: nodejs16.x
Memory: 512MB
Timeout: 45s
Parameters:
  - quality: string (compression level - low, medium, high)
  - downsampleImages: boolean (Reduce image resolution)
  - imageQuality: number (Quality of embedded images)
  - removeMetadata: boolean (Strip document metadata)
Dependencies:
  - pdf-lib
  - sharp
  - ghostscript (via layer)
Output: Compressed PDF file
```

### 6. Remove Blank Pages (`aipdf-processing-remove-blanks`)

```yaml
Name: aipdf-processing-remove-blanks
Description: Detects and removes blank or nearly blank pages
Runtime: nodejs16.x
Memory: 512MB
Timeout: 30s
Parameters:
  - threshold: number (Blank detection threshold, 0-100)
  - includeUncertainPages: boolean (Remove pages that might have minimal content)
Dependencies:
  - pdf-lib
  - pdfjs-dist
  - sharp (for image analysis)
Output: PDF file with blank pages removed
```

### 7. Rotate Pages (`aipdf-processing-rotate`)

```yaml
Name: aipdf-processing-rotate
Description: Rotates PDF pages
Runtime: nodejs16.x
Memory: 512MB
Timeout: 30s
Parameters:
  - angle: number (Rotation angle, typically 90, 180, or 270)
  - pages: array[number] (Specific pages to rotate, empty for all)
Dependencies:
  - pdf-lib
Output: PDF file with rotated pages
```

### 8. Split/Merge PDFs (`aipdf-processing-split-merge`)

```yaml
Name: aipdf-processing-split-merge
Description: Splits PDF into multiple files or merges multiple PDFs
Runtime: nodejs16.x
Memory: 512MB
Timeout: 45s
Parameters:
  - mode: string (split or merge)
  - splitPages: array[number] (Page numbers to split at)
  - mergeFiles: array[string] (S3 keys of files to merge)
  - outputFormat: string (single ZIP file or multiple PDF files)
Dependencies:
  - pdf-lib
Output: ZIP file containing multiple PDFs or single merged PDF
```

### 9. Watermark (`aipdf-processing-watermark`)

```yaml
Name: aipdf-processing-watermark
Description: Adds or removes watermarks from PDF pages
Runtime: nodejs16.x
Memory: 512MB
Timeout: 30s
Parameters:
  - action: string (add or remove)
  - text: string (Watermark text for adding)
  - image: string (S3 key to image for adding)
  - opacity: number (Watermark opacity, 0-1)
  - position: string (center, top, bottom, etc.)
  - pages: array[number] (Specific pages to watermark, empty for all)
Dependencies:
  - pdf-lib
  - sharp (for image watermarks)
Output: PDF file with watermarks added or removed
```

### 10. Redact Content (`aipdf-processing-redact`)

```yaml
Name: aipdf-processing-redact
Description: Redacts text and images based on patterns
Runtime: nodejs16.x
Memory: 1024MB
Timeout: 60s
Parameters:
  - patterns: array[string] (Regex patterns to redact)
  - replaceWith: string (Replacement text, default block rectangle)
  - includeImages: boolean (Whether to redact images containing matched text)
  - ocrImages: boolean (Whether to OCR images for text)
Dependencies:
  - pdf-lib
  - pdfjs-dist
  - tesseract.js (for OCR)
Output: PDF file with redacted content
```

### 11. Summarize Content (`aipdf-processing-summarize`)

```yaml
Name: aipdf-processing-summarize
Description: Generates AI summary of PDF content
Runtime: nodejs16.x
Memory: 1024MB
Timeout: 120s
Parameters:
  - maxLength: number (Maximum summary length in words)
  - style: string (brief, detailed, bullet-points, etc.)
  - focusArea: string (specific aspect to focus on)
  - model: string (LLM model to use)
Dependencies:
  - pdf-lib
  - pdfjs-dist
  - openai (or other LLM client)
Output: Text file containing the summary
```

## Monolithic Option (`aipdf-processing-engine`)

If implementing all functions in a single Lambda:

```yaml
Name: aipdf-processing-engine
Description: Comprehensive PDF processing engine
Runtime: nodejs16.x
Memory: 1024MB
Timeout: 120s
Parameters:
  - action: string (resize, extract-text, compress, etc.)
  - actionParameters: object (Parameters specific to the action)
  - inputBucket: string (S3 bucket containing input PDF)
  - inputKey: string (S3 key for input PDF)
  - outputBucket: string (S3 bucket for processed output)
  - outputKey: string (S3 key for output file)
Dependencies:
  - All dependencies from individual functions
Output: Processed file according to action
```

## Lambda Layers

### PDF Utilities Layer

```yaml
Name: aipdf-processing-pdf-utils
Description: Common PDF processing libraries and utilities
Runtime: nodejs16.x
Content:
  - pdf-lib (PDF creation and manipulation)
  - pdfjs-dist (PDF parsing and content extraction)
  - sharp (Image processing)
  - archiver (ZIP file creation)
  - aws-sdk (S3 and DynamoDB access)
Size: ~50MB compressed
```

### OCR Utilities Layer

```yaml
Name: aipdf-processing-ocr-utils
Description: OCR functionality for text extraction
Runtime: nodejs16.x
Content:
  - tesseract.js
  - language data for common languages
Size: ~100MB compressed
```

### Implementation Notes

1. Each function should include robust error handling with detailed logs
2. Use AWS X-Ray for tracing execution flow
3. Implement exponential backoff for retries
4. Cache downloaded files in /tmp to avoid repeated S3 downloads
5. Consider using Provisioned Concurrency for frequently used functions
6. Implement input validation before processing
7. Store job details in DynamoDB for tracking and history