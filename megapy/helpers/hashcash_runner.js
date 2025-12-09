// Wrapper script to run hashcash generation from command line
import { generateHashcashToken } from './hashcash.js';

const challenge = process.argv[2];
if (!challenge) {
    console.error(JSON.stringify({ success: false, error: 'No challenge provided' }));
    process.exit(1);
}

try {
    const result = await generateHashcashToken(challenge);
    console.log(JSON.stringify({ success: true, result: result }));
} catch (error) {
    console.error(JSON.stringify({ success: false, error: error.message }));
    process.exit(1);
}

