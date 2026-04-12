import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';
import { fromCognitoIdentityPool } from '@aws-sdk/credential-providers';
import { config } from './config';

export async function uploadToS3(file: File, todoID: string): Promise<string> {
    const userID = localStorage.getItem('userID') ?? 'unknown';
    const key = `${userID}/${todoID}/${crypto.randomUUID()}-${file.name}`;

    const credentials = fromCognitoIdentityPool({
        clientConfig: { region: config.awsRegion },
        identityPoolId: config.cognitoIdentityPoolId,
    });

    const s3 = new S3Client({
        region: config.awsRegion,
        credentials,
    });

    await s3.send(new PutObjectCommand({
        Bucket: config.s3Bucket,
        Key: key,
        Body: file,
        ContentType: file.type,
    }));

    return key;
}
