<?php

namespace App\Http\Middleware;

use Closure;
use App\Models\LoginUsers;
use Carbon\Carbon;

class VerifyToken
{

    public function __construct(){

    }
    /**
     * Handle an incoming request.
     *
     * @param  \Illuminate\Http\Request  $request
     * @param  \Closure  $next
     * @return mixed
     */
    public function handle($request, Closure $next)
    {
        $token = $request->apikey;
        
        try {
            if (! $token) {
                throw new \Exception('Access forbidden.');
            }

            $user = LoginUsers::where("api_token",$token)->where("status", true)->first();

            if ($user == null) {
                throw new \Exception('Invalid access token.');
            }

            $request->userinfo = $user;

        } catch (\Exception $e) {
            return response()->json(['status' => 'error', 'message' => $e->getMessage()]);
        }

        return $next($request);
    }
}
